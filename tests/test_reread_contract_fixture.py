import copy
import json
from pathlib import Path
import re
import unittest

from legion_tabula.corpus import CorpusReadError, CorpusReference, ScopeBinding, TabulaCorpusClient
from legion_tabula.mcp import McpResponse


class RereadContractFixtureTests(unittest.TestCase):
    def test_shared_ordered_unicode_fixture_and_reordered_response(self):
        fixture = json.loads((Path(__file__).parent / "contracts/tabula-corpus-reread-v1.json").read_text())
        arguments = fixture["request"]
        records = fixture["response"]["results"]
        refs = tuple(CorpusReference(**ref, canonical_uri=record["canonical_uri"])
                     for ref, record in zip(arguments["references"], records, strict=True))
        for reordered in (False, True):
            def transport(token, call):
                token()
                response = copy.deepcopy(fixture["response"])
                response["request_id"] = call["arguments"]["request_id"]
                if reordered:
                    response["results"].reverse()
                return McpResponse(200, response)
            client = TabulaCorpusClient(transport)
            def read():
                return client.reread(token=lambda: "synthetic", binding=ScopeBinding(**arguments["binding"]),
                    references=refs, correlation_id=arguments["correlation_id"])
            if reordered:
                with self.assertRaisesRegex(CorpusReadError, "TABULA_PROTOCOL_ERROR"):
                    read()
            else:
                self.assertEqual([record.content for record in read().records], ["ab😀", "tiny"])
        schema = json.loads((Path(__file__).parents[1] / "schemas/tabula-corpus-reread.schema.json").read_text())
        pattern = schema["$defs"]["binding_reference"]["properties"]["version"]["pattern"]
        self.assertTrue(re.fullmatch(pattern, arguments["binding"]["version"]))
        self.assertFalse(re.fullmatch(pattern, "1x0x0"))
