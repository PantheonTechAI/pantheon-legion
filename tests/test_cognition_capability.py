from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timezone
import unittest

from legion_resource import ComputeNode, InferenceEndpoint, InferenceTopologyCatalog, NodeObservation
from legion_cognition.capability import (
    CognitionError, CognitionOfferingCatalog, CognitionRequirement, CognitionRouter,
    InferenceProvider, ModelOffering, OfferingObservation, OfferingValidationRecord,
)


FEATURES = ("reasoning", "tool_calls", "separated_reasoning")
NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


def catalog(origin="https://inference.example", revision="catalog-a"):
    resources = InferenceTopologyCatalog(revision, (ComputeNode("node-a", "LOCAL", "homelab"),),
                                        (InferenceEndpoint("endpoint-a", "node-a", origin),))
    provider = InferenceProvider("provider-a", "endpoint-a", "openai-compatible", "fixture", "1", "separated")
    validation = OfferingValidationRecord(provider.provider_id, "fixture", "1", "model-a", "separated",
                                         FEATURES, "2026-09-01T00:00:00Z", "2099-01-01T00:00:00Z")
    offering = ModelOffering("offering-a", provider.provider_id, "model-a", 32768, FEATURES, validation)
    return resources, CognitionOfferingCatalog(revision, (provider,), (offering,))


class Probe:
    def __init__(self):
        self.calls = []
        self.healthy = True

    def available(self, endpoint, provider, offering):
        self.calls.append((endpoint.endpoint_id, provider.provider_id, offering.offering_id))
        return self.healthy


class CognitionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.resources, self.catalog = catalog()
        self.probe = Probe()
        self.router = CognitionRouter(self.resources, self.catalog, self.probe, clock=lambda: NOW)

    def test_selection_preserves_all_identities_without_resource_fields_in_requirement(self):
        requirement = CognitionRequirement()
        selection = self.router.select(requirement)
        self.assertEqual(asdict(selection), dict(catalog_revision="catalog-a", offering_id="offering-a",
                         provider_id="provider-a", endpoint_id="endpoint-a", node_id="node-a"))
        self.assertFalse(set(asdict(selection)) & set(asdict(requirement)))
        with self.assertRaises(FrozenInstanceError):
            self.resources.nodes[0].node_id = "changed"

    def test_hard_constraints_and_conformance_fail_before_probe(self):
        for field, value in (("minimum_context", 65536), ("capability", "vision"),
                             ("data_classification", "secret"), ("trust_zone", "other")):
            with self.subTest(field=field), self.assertRaises(CognitionError):
                self.router.select(replace(CognitionRequirement(), **{field: value}))
        self.assertEqual(self.probe.calls, [])
        for provider in (replace(self.catalog.providers[0], runtime_version="2"),
                         replace(self.catalog.providers[0], enabled=False)):
            router = CognitionRouter(self.resources, replace(self.catalog, providers=(provider,)), self.probe,
                                     clock=lambda: NOW)
            with self.assertRaises(CognitionError):
                router.select(CognitionRequirement())
        self.assertEqual(self.probe.calls, [])
        self.probe.healthy = False
        with self.assertRaises(CognitionError):
            self.router.select(CognitionRequirement())

    def test_graph_integrity_precedes_network_and_identity_cardinalities(self):
        with self.assertRaises(ValueError):
            replace(self.resources, nodes=())
        with self.assertRaises(ValueError):
            replace(self.catalog, providers=())
        with self.assertRaises(ValueError):
            replace(self.catalog, providers=self.catalog.providers * 2)
        with self.assertRaises(ValueError):
            CognitionRouter(self.resources, replace(self.catalog, catalog_revision="different"), self.probe)
        with self.assertRaises(ValueError):
            replace(self.catalog, providers=self.catalog.providers +
                    (replace(self.catalog.providers[0], provider_id="other"),))
        self.assertEqual(self.probe.calls, [])

    def test_many_endpoints_models_and_same_model_on_another_node(self):
        resources = replace(self.resources, nodes=self.resources.nodes + (ComputeNode("node-b", "LOCAL", "homelab"),),
                            endpoints=self.resources.endpoints +
                            (InferenceEndpoint("endpoint-b", "node-a", "https://second.example"),
                             InferenceEndpoint("endpoint-c", "node-b", "https://third.example")))
        providers = self.catalog.providers + tuple(replace(self.catalog.providers[0], provider_id="provider-" + x,
                                                          endpoint_id="endpoint-" + x) for x in ("b", "c"))
        original = self.catalog.offerings[0]
        offerings = (original, replace(original, offering_id="another-model", model_id="model-b",
                                      validation_record=replace(original.validation_record, model_id="model-b")),
                     replace(original, offering_id="same-model-other-node", provider_id="provider-c", priority=1,
                             validation_record=replace(original.validation_record, provider_id="provider-c")))
        router = CognitionRouter(resources, replace(self.catalog, providers=providers, offerings=offerings), self.probe,
                                 clock=lambda: NOW)
        self.assertEqual(router.select(CognitionRequirement()).node_id, "node-b")

    def test_revision_replacement_preserves_historical_selection_and_rejects_stale_retry(self):
        requirement = CognitionRequirement()
        old = self.router.select(requirement)
        resources = replace(self.resources, catalog_revision="catalog-b",
                            nodes=(ComputeNode("node-b", "LOCAL", "homelab"),),
                            endpoints=(replace(self.resources.endpoints[0], node_id="node-b"),))
        with self.assertRaisesRegex(ValueError, "IMMUTABLE"):
            self.router.update_catalog(replace(resources, catalog_revision="catalog-a"), self.catalog)
        self.router.update_catalog(resources, replace(self.catalog, catalog_revision="catalog-b"))
        with self.assertRaisesRegex(CognitionError, "SELECTION_STALE"):
            self.router.resolve(old, requirement)
        self.assertEqual((old.catalog_revision, old.node_id), ("catalog-a", "node-a"))
        self.assertEqual(self.router.select(requirement).node_id, "node-b")

    def test_endpoint_safety_and_observation_ownership(self):
        for origin in ("file:///etc/passwd", "https://user:secret@host", "https://host/v1", "https://host?",
                       "https://host#", "https://host\\other", "https://host\n", "https://host:0"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                InferenceEndpoint("e", "n", origin)
        with self.assertRaises(ValueError):
            NodeObservation("n", "decode_throughput", 80.8, "tokens-per-second", NOW.isoformat())
        observation = OfferingObservation("o", "decode_throughput", 80.8, "tokens-per-second", NOW.isoformat())
        self.assertEqual(observation.offering_id, "o")
