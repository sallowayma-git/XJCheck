from __future__ import annotations

from dataclasses import replace

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import ConnectivityAssertionState
from dwg_audit.audit.symbol_dependency_library import GeometryDefinition
from dwg_audit.audit.symbol_dependency_library import GeometryDefinitionDependency
from dwg_audit.audit.symbol_dependency_library import GeometryIdentity
from dwg_audit.audit.symbol_dependency_library import InternalConnectivityGroup
from dwg_audit.audit.symbol_dependency_library import NestedPortBinding
from dwg_audit.audit.symbol_dependency_library import PortType
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependency
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_dependency_library import SymbolPort
from dwg_audit.audit.symbol_dependency_library import ValidationSeverity


def _identity(family: str, fingerprint: str | None = None) -> SymbolIdentity:
    return SymbolIdentity(
        family=family,
        version="1.0.0",
        fingerprint=fingerprint or f"fp-{family.casefold()}",
    )


def _confirmed_port(
    port_id: str,
    position: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> SymbolPort:
    return SymbolPort(
        port_id=port_id,
        local_position=position,
        outward_direction=direction,
        port_type=PortType.ELECTRICAL,
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
    )


def _registered_switch() -> tuple[GeometryDefinition, SymbolDefinition]:
    geometry_identity = GeometryIdentity("switch-geometry", "1", "geo-fp-switch")
    geometry = GeometryDefinition(identity=geometry_identity)
    symbol = SymbolDefinition(
        identity=_identity("switch"),
        geometry_dependencies=(
            GeometryDefinitionDependency("body", geometry_identity),
        ),
        ports=(
            _confirmed_port("A", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            _confirmed_port("B", (10.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
        internal_connectivity_groups=(
            InternalConnectivityGroup(
                group_id="closed-path",
                port_ids=("A", "B"),
                state=ConnectivityAssertionState.ASSERTED,
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
                source_ids=("review-1",),
            ),
        ),
        aliases=(SymbolAlias("SW", source_id="review-1"),),
        sources=(
            SourceReference(
                source_id="review-1",
                source_kind="HUMAN_REVIEW",
                locator="review/switch-v1.json",
            ),
        ),
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
        registry_status=RegistryStatus.REGISTERED,
        critical_issue_eligible=True,
    )
    return geometry, symbol


def _issue_codes(library: SymbolDependencyLibrary) -> set[str]:
    return {issue.code for issue in library.validate().issues}


def test_registered_human_confirmed_symbol_can_drive_critical_and_union() -> None:
    geometry, symbol = _registered_switch()
    library = SymbolDependencyLibrary(
        symbols=(symbol,), geometry_definitions=(geometry,)
    )

    validation = library.validate()

    assert validation.valid is True
    assert library.resolve(symbol.identity) == symbol
    assert library.resolve_alias("sw") == symbol
    assert library.can_drive_critical(symbol.identity) is True
    assert library.can_assert_electrical_union(symbol.identity, "a", "B") is True
    assert library.can_assert_electrical_union(symbol.identity, "A", "A") is False
    payload = library.to_dict()
    assert payload["schema_version"] == "symbol-dependency-library-v1"
    assert payload["symbols"][0]["family"] == "switch"
    assert payload["symbols"][0]["ports"][0]["local_position"] == [0.0, 0.0, 0.0]
    assert (
        payload["symbols"][0]["internal_connectivity_groups"][0]["state"]
        == "ASSERTED"
    )


def test_duplicate_ports_are_case_insensitive_and_fail_closed() -> None:
    geometry, symbol = _registered_switch()
    symbol = replace(
        symbol,
        ports=(symbol.ports[0], replace(symbol.ports[1], port_id="a")),
    )
    library = SymbolDependencyLibrary((symbol,), (geometry,))

    assert "DUPLICATE_PORT_ID" in _issue_codes(library)
    assert library.can_drive_critical(symbol.identity) is False
    assert library.can_assert_electrical_union(symbol.identity, "A", "B") is False


def test_required_dangling_geometry_and_symbol_dependencies_are_errors() -> None:
    symbol = SymbolDefinition(
        identity=_identity("panel"),
        geometry_dependencies=(
            GeometryDefinitionDependency(
                "missing-geometry",
                GeometryIdentity("missing", "1", "missing-fp"),
            ),
        ),
        symbol_dependencies=(
            SymbolDependency("missing-child", _identity("missing-child")),
        ),
    )
    library = SymbolDependencyLibrary(symbols=(symbol,))

    validation = library.validate()

    assert validation.valid is False
    assert {
        "DANGLING_GEOMETRY_DEPENDENCY",
        "DANGLING_SYMBOL_DEPENDENCY",
    }.issubset(_issue_codes(library))


def test_optional_dangling_dependency_is_warning_but_not_error() -> None:
    symbol = SymbolDefinition(
        identity=_identity("optional-parent"),
        symbol_dependencies=(
            SymbolDependency(
                "optional-child",
                _identity("optional-child"),
                required=False,
            ),
        ),
    )
    validation = SymbolDependencyLibrary(symbols=(symbol,)).validate()

    dangling = next(
        issue
        for issue in validation.issues
        if issue.code == "DANGLING_SYMBOL_DEPENDENCY"
    )
    assert dangling.severity is ValidationSeverity.WARNING
    assert validation.valid is True


def test_nested_symbol_dependency_cycle_is_rejected() -> None:
    first_identity = _identity("first")
    second_identity = _identity("second")
    first = SymbolDefinition(
        identity=first_identity,
        symbol_dependencies=(SymbolDependency("to-second", second_identity),),
    )
    second = SymbolDefinition(
        identity=second_identity,
        symbol_dependencies=(SymbolDependency("to-first", first_identity),),
    )
    library = SymbolDependencyLibrary(symbols=(first, second))

    validation = library.validate()

    cycle_issue = next(
        issue for issue in validation.issues if issue.code == "SYMBOL_DEPENDENCY_CYCLE"
    )
    assert validation.valid is False
    assert set(cycle_issue.cycle) == {
        first_identity.canonical_id,
        second_identity.canonical_id,
    }


def test_unconfirmed_port_cannot_be_promoted_to_critical() -> None:
    geometry, symbol = _registered_switch()
    symbol = replace(
        symbol,
        ports=(
            replace(
                symbol.ports[0],
                annotation_status=AnnotationStatus.MACHINE_PROPOSED,
            ),
            symbol.ports[1],
        ),
    )
    library = SymbolDependencyLibrary((symbol,), (geometry,))

    codes = _issue_codes(library)

    assert "CRITICAL_REQUIRES_CONFIRMED_PORTS" in codes
    assert "ASSERTED_UNION_REQUIRES_CONFIRMED_PORTS" in codes
    assert library.can_drive_critical(symbol.identity) is False
    assert library.can_assert_electrical_union(symbol.identity, "A", "B") is False


def test_unknown_symbol_never_drives_critical_or_asserted_union() -> None:
    unknown_identity = _identity("unknown")
    unknown = SymbolDefinition(
        identity=unknown_identity,
        ports=(
            SymbolPort(
                port_id="P1",
                local_position=(0.0, 0.0, 0.0),
                outward_direction=(1.0, 0.0, 0.0),
            ),
            SymbolPort(
                port_id="P2",
                local_position=(1.0, 0.0, 0.0),
                outward_direction=(-1.0, 0.0, 0.0),
            ),
        ),
        internal_connectivity_groups=(
            InternalConnectivityGroup(
                group_id="machine-guess",
                port_ids=("P1", "P2"),
                state=ConnectivityAssertionState.POSSIBLE,
            ),
        ),
    )
    library = SymbolDependencyLibrary(symbols=(unknown,))

    assert library.validate().valid is True
    assert library.can_drive_critical(unknown_identity) is False
    assert library.can_assert_electrical_union(unknown_identity, "P1", "P2") is False
    assert library.can_drive_critical(_identity("not-in-library")) is False
    assert (
        library.can_assert_electrical_union(
            _identity("not-in-library"), "P1", "P2"
        )
        is False
    )


def test_asserted_union_requires_human_confirmation() -> None:
    geometry, symbol = _registered_switch()
    symbol = replace(
        symbol,
        critical_issue_eligible=False,
        internal_connectivity_groups=(
            replace(
                symbol.internal_connectivity_groups[0],
                annotation_status=AnnotationStatus.MACHINE_PROPOSED,
            ),
        ),
    )
    library = SymbolDependencyLibrary((symbol,), (geometry,))

    assert "ASSERTED_UNION_REQUIRES_HUMAN_CONFIRMATION" in _issue_codes(library)
    assert library.can_assert_electrical_union(symbol.identity, "A", "B") is False


def test_unknown_nested_symbol_cannot_indirectly_enable_critical() -> None:
    geometry, parent = _registered_switch()
    child = SymbolDefinition(identity=_identity("unknown-child"))
    parent = replace(
        parent,
        symbol_dependencies=(
            SymbolDependency("nested-child", child.identity),
        ),
    )
    library = SymbolDependencyLibrary((parent, child), (geometry,))

    assert "CRITICAL_REQUIRES_CONFIRMED_DEPENDENCIES" in _issue_codes(library)
    assert library.can_drive_critical(parent.identity) is False


def test_unknown_nested_symbol_cannot_indirectly_enable_asserted_union() -> None:
    geometry, parent = _registered_switch()
    child = SymbolDefinition(
        identity=_identity("unknown-child"),
        ports=(
            SymbolPort(
                port_id="C1",
                local_position=(0.0, 0.0, 0.0),
                outward_direction=(1.0, 0.0, 0.0),
            ),
        ),
    )
    parent = replace(
        parent,
        critical_issue_eligible=False,
        symbol_dependencies=(
            SymbolDependency(
                "nested-child",
                child.identity,
                port_bindings=(NestedPortBinding("A", "C1"),),
            ),
        ),
    )
    library = SymbolDependencyLibrary((parent, child), (geometry,))

    assert (
        "ASSERTED_UNION_REQUIRES_CONFIRMED_DEPENDENCIES"
        in _issue_codes(library)
    )
    assert library.can_assert_electrical_union(parent.identity, "A", "B") is False


def test_nested_port_bindings_must_resolve_on_parent_and_child() -> None:
    child = SymbolDefinition(
        identity=_identity("child"),
        ports=(
            _confirmed_port("C1", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
    )
    parent = SymbolDefinition(
        identity=_identity("parent"),
        ports=(
            _confirmed_port("P1", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
        ),
        symbol_dependencies=(
            SymbolDependency(
                dependency_id="child-instance",
                target=child.identity,
                port_bindings=(
                    NestedPortBinding("missing-parent", "missing-child"),
                ),
            ),
        ),
    )
    library = SymbolDependencyLibrary(symbols=(parent, child))

    codes = _issue_codes(library)

    assert "DANGLING_PARENT_PORT_BINDING" in codes
    assert "DANGLING_CHILD_PORT_BINDING" in codes


def test_ambiguous_alias_and_duplicate_definition_do_not_resolve() -> None:
    first = SymbolDefinition(
        identity=_identity("first"), aliases=(SymbolAlias("K1"),)
    )
    second = SymbolDefinition(
        identity=_identity("second"), aliases=(SymbolAlias("k1"),)
    )
    duplicate = replace(first)
    library = SymbolDependencyLibrary(symbols=(first, second, duplicate))

    codes = _issue_codes(library)

    assert "AMBIGUOUS_SYMBOL_ALIAS" in codes
    assert "DUPLICATE_SYMBOL_DEFINITION" in codes
    assert library.resolve(first.identity) is None
    assert library.resolve_alias("K1") is None
