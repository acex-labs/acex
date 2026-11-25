"""The filters of a generated ConfigMap: several of them apply together (all) unless the request says any one is
enough, and the generated code means what the request meant."""

from types import SimpleNamespace

import pytest
from acex.api.routers.config_components import (
    ComponentInstance,
    FilterSpec,
    GenerateRequest,
    ReconcileOptions,
    TranslateRequest,
    generate_configmap,
)

HOSTNAME = ComponentInstance(component="HostName", variable_name="hostname", values={"name": "sw-1"})
CORE_AT_GOT = [FilterSpec(attribute="site", value="got"), FilterSpec(attribute="role", value="core")]


def filters_of(code: str):
    """What the generated ConfigMap's filters are, by running the generated code."""
    namespace: dict = {}
    exec(code, namespace)  # noqa: S102 - code made by generate_configmap from a request in this test
    return namespace["demo"].filters


def node(**fields):
    return SimpleNamespace(**{"role": "core", "site": "got", "hostname": "sw-1", "sequence": 1, **fields})


def generated(filters, **request):
    return generate_configmap(GenerateRequest(class_name="Demo", filter=filters, components=[HOSTNAME], **request)).code


def test_several_filters_all_have_to_match_by_default():
    filters = filters_of(generated(CORE_AT_GOT))

    assert filters.match(node())
    assert not filters.match(node(site="sto"))
    assert not filters.match(node(role="access"))
    assert not filters.match(node(site="sto", role="access"))


def test_any_one_of_the_filters_is_enough_when_the_request_says_so():
    filters = filters_of(generated(CORE_AT_GOT, filter_match="any"))

    assert filters.match(node())
    assert filters.match(node(site="sto"))
    assert filters.match(node(role="access"))
    assert not filters.match(node(site="sto", role="access"))


def test_one_filter_is_the_same_whichever_way_they_are_combined():
    one = [FilterSpec(attribute="site", value="got")]

    for match in ("all", "any"):
        filters = filters_of(generated(one, filter_match=match))
        assert filters.match(node())
        assert not filters.match(node(site="sto"))


def test_no_filter_leaves_the_configmap_without_one():
    assert filters_of(generated(None)) is None


def test_three_filters_and_a_regular_expression():
    filters = filters_of(
        generated(
            [
                FilterSpec(attribute="site", value="got"),
                FilterSpec(attribute="role", operator="ne", value="access"),
                FilterSpec(attribute="hostname", value="/sw-[0-9]+/"),
            ]
        )
    )

    assert filters.match(node())
    assert not filters.match(node(role="access"))
    assert not filters.match(node(hostname="router-1"))


@pytest.mark.parametrize("request_model", [ReconcileOptions, TranslateRequest])
def test_the_other_requests_take_the_same_setting(request_model):
    fields = {"ned_id": "x", "config_text": "y"} if request_model is TranslateRequest else {}

    assert request_model(**fields).filter_match == "all"
    assert request_model(filter_match="any", **fields).filter_match == "any"
    with pytest.raises(ValueError):
        request_model(filter_match="both", **fields)
