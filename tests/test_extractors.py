import pytest

from ddr.powerbi import BimParseError, extract as extract_bim
from ddr.refs import ColumnRef
from ddr.simulator import make_bim, make_twb
from ddr.tableau import TwbParseError, extract as extract_twb

CR = ColumnRef.make


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_twb_columns_extracted(tmp_path):
    p = write(tmp_path, "wb.twb", make_twb("wb", "fct_sales", ["revenue", "sale_date"]))
    refs = extract_twb(p).refs
    assert CR("fct_sales", "revenue") in refs
    assert CR("fct_sales", "sale_date") in refs


def test_twb_alias_resolves_to_physical_table(tmp_path):
    """A datasource can alias the relation ('Orders' for fct_sales); map
    values reference the alias, and refs must resolve to the physical table."""
    twb = """<?xml version='1.0'?>
<workbook name="aliased">
  <datasources><datasource name="wh">
    <relation name="Orders" table="[main].[fct_sales]" type="table"/>
    <map key="[revenue]" value="[Orders].[revenue]"/>
  </datasource></datasources>
</workbook>"""
    refs = extract_twb(write(tmp_path, "a.twb", twb)).refs
    assert refs == {CR("fct_sales", "revenue")}


def test_twb_case_folding(tmp_path):
    twb = """<?xml version='1.0'?>
<workbook name="cased">
  <datasources><datasource name="wh">
    <relation name="FCT_SALES" table="[MAIN].[FCT_SALES]" type="table"/>
    <map key="[REVENUE]" value="[FCT_SALES].[REVENUE]"/>
  </datasource></datasources>
</workbook>"""
    refs = extract_twb(write(tmp_path, "c.twb", twb)).refs
    assert refs == {CR("fct_sales", "revenue")}


def test_twb_invalid_xml_raises(tmp_path):
    with pytest.raises(TwbParseError):
        extract_twb(write(tmp_path, "bad.twb", "<workbook><unclosed>"))


def test_bim_physical_columns_and_measure_refs(tmp_path):
    p = write(tmp_path, "m.bim", make_bim())
    refs = extract_bim(p).refs
    assert CR("fct_sales", "revenue") in refs      # physical via sourceColumn
    assert CR("fct_sales", "quantity") in refs     # referenced in a measure
    assert CR("dim_customers", "segment") in refs


def test_bim_quoted_table_dax_reference(tmp_path):
    import json

    model = {"name": "m", "model": {"tables": [{
        "name": "S", "source": "fct_sales", "columns": [],
        "measures": [{"name": "x",
                      "expression": "CALCULATE(SUM('fct_sales'[revenue]))"}],
    }]}}
    refs = extract_bim(write(tmp_path, "q.bim", json.dumps(model))).refs
    assert CR("fct_sales", "revenue") in refs


def test_bim_invalid_json_and_shape(tmp_path):
    with pytest.raises(BimParseError, match="not valid JSON"):
        extract_bim(write(tmp_path, "bad.bim", "{broken"))
    with pytest.raises(BimParseError, match="no tables"):
        extract_bim(write(tmp_path, "shape.bim", "{}"))
