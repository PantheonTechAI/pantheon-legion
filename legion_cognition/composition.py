"""Explicit trusted static composition, disabled until an operator enables it."""

import json
import os
from pathlib import Path

from legion_resource import ComputeNode, InferenceEndpoint, InferenceTopologyCatalog
from .authorized import AuthorizedCognitionInvoker
from .capability import (
    CognitionError, CognitionOfferingCatalog, CognitionRouter,
    InferenceProvider, ModelOffering, OfferingValidationRecord,
)
from .openai_compatible import OpenAICompatibleTransport, TransportPolicy, strict_json


def environment_secret(reference):
    if not reference.startswith("env:"):
        raise ValueError("UNSUPPORTED_SECRET_REFERENCE")
    return os.environ[reference[4:]]


def load_catalog(path):
    try:
        with Path(path).open("rb") as source:
            body = source.read(65537)
        if len(body) > 65536:
            raise ValueError
        config = strict_json(body)
        if set(config) != {"enabled", "catalog_revision", "nodes", "endpoints", "providers", "offerings"}:
            raise ValueError
        if config["enabled"] is not True:
            raise CognitionError("COGNITION_CONFIGURATION_DISABLED")
        resources = InferenceTopologyCatalog(config["catalog_revision"],
            tuple(ComputeNode(**item) for item in config["nodes"]),
            tuple(InferenceEndpoint(**item) for item in config["endpoints"]))
        providers = tuple(InferenceProvider(**item) for item in config["providers"])
        offerings = []
        for item in config["offerings"]:
            item = dict(item)
            record = dict(item.pop("validation_record"))
            record["features"] = tuple(record["features"])
            item["features"] = tuple(item["features"])
            if "data_classifications" in item:
                item["data_classifications"] = tuple(item["data_classifications"])
            offerings.append(ModelOffering(**item, validation_record=OfferingValidationRecord(**record)))
        return resources, CognitionOfferingCatalog(config["catalog_revision"], providers, tuple(offerings))
    except CognitionError:
        raise
    except (ValueError, TypeError, KeyError, OSError):
        raise CognitionError("COGNITION_CONFIGURATION_INVALID") from None


def configured_cognition(path, authority, *, policy=TransportPolicy(), secret_supplier=environment_secret):
    resources, offerings = load_catalog(path)
    transport = OpenAICompatibleTransport(policy=policy, secret_supplier=secret_supplier)
    for provider in offerings.providers:
        if provider.enabled:
            transport.validate_configuration(resources.resolve_endpoint(provider.endpoint_id), provider)
    return AuthorizedCognitionInvoker(CognitionRouter(resources, offerings, transport), transport, authority)
