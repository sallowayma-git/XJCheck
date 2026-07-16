"""Geometry-driven MACHINE_PROPOSED symbol port candidates.

Proposals are fail-closed draft annotations only:
- port / symbol annotation_status = MACHINE_PROPOSED
- registry_status remains UNKNOWN
- critical_issue_eligible remains false
- connectivity groups stay UNKNOWN / MACHINE_PROPOSED

They never count as human confirmation and cannot flip primary_engine.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations, permutations
from pathlib import Path
from typing import Any


PROPOSAL_SCHEMA_VERSION = "symbol-port-proposal-v1"
SOURCE_KIND = "machine_geometry_proposal"
FAMILY_CLASSIFICATION_VERSION = "symbol-family-classification-v1"
BEHAVIOR_POLICY_VERSION = "symbol-behavior-policy-v1"
GEOMETRY_IGNORE_FAMILIES = frozenset(
    {
        "non_electrical.numeric_text.v1",
        "non_electrical.graphic.v1",
        "non_electrical.functional_graphic.v1",
        "non_electrical.equipment_graphic.v1",
        "non_electrical.placeholder.v1",
        "non_electrical.drawing_metadata.v1",
        "switch.open.v1",
        "line_break.non_connective.v1",
        "communication.ethernet_port_ignored.v1",
        "communication.optical_st_port_ignored.v1",
        "communication.remote_interface_marker_ignored.v1",
        "communication.equipment_panel_ignored.v1",
        "electrical.ground_symbol_ignored.v1",
        "electrical.nonconnective_four_coil_ignored.v1",
        "electrical.nonconnective_repeated_coil_panel_ignored.v1",
        "electrical.nonconnective_stepped_marker_ignored.v1",
        "electrical.diode_symbol_ignored.v1",
        "electrical.nonconnective_dzb_right_marker_ignored.v1",
        "electrical.nonconnective_three_lead_box_ignored.v1",
        "electrical.nonconnective_dual_row_signal_panel_ignored.v1",
        "electrical.nonconnective_inline_indicator_ignored.v1",
        "electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1",
        "non_electrical.cable_sleeve_ignored.v1",
        "electrical.nonconnective_circle_contact_marker_ignored.v1",
        "electrical.nonconnective_crossed_circle_marker_ignored.v1",
        "electrical.nonconnective_actuated_open_switch_ignored.v1",
        "electrical.nonconnective_wide_contact_cap_marker_ignored.v1",
        "electrical.nonconnective_vertical_zigzag_element_ignored.v1",
        "electrical.nonconnective_inline_rectangle_ignored.v1",
        "electrical.nonconnective_dual_row_arc_motif_ignored.v1",
        "electrical.nonconnective_switch_class_ignore.v1",
        "electrical.nonconnective_led_arrow_ignored.v1",
        "electrical.nonconnective_narrow_frame_ignored.v1",
    }
)
TABLE_CONTAINER_FAMILIES = frozenset({"structural.backplate_table_container.v1"})
WIRE_PRIMITIVE_FAMILIES = frozenset({"wire.crossover_jump.v1"})

# Human adjudications are keyed exclusively by observed geometry fingerprint.
# Block names are deliberately not used as a fallback: the same name may have
# different geometry and semantics in another project/version.
HUMAN_SYMBOL_PORT_POLICIES: dict[str, dict[str, str]] = {
    **{
        fp: {
            "mode": "IGNORE_ELECTRICAL",
            "family_id": "electrical.nonconnective_switch_class_ignore.v1",
            "reason": "Historical switch authority: complete actuated switch artwork is ignored and emits zero electrical semantics.",
        }
        for fp in (
            "b925541c91034677347b986a38b2f9f6fbfdc74ddc28e59d926a527e468b0835",
            "002217bb22cc51b96e9c88e62e66c6ecb6445eb40ca18100997622df676687f7",
            "5cd8c1470ed3c9d776bb695fb76434e98a0030409a04e5a58ec703994ee71c99",
            "75ec9dd5a7d1692a60f19c598f4d2a20cb6e706727a34dce66bdc700b2c750f8",
        )
    },
    "ccb29346ae9a189136431ed0b773d30d319ed1bd7d009fed79702f6ff92fed85": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_switch_class_ignore.v1",
        "reason": "Historical switch authority: ignore the complete three-contact selector artwork; emit no ports, mappings, connectivity, or union.",
    },
    "888624f490c7130e32d2b3bdfcaded86643f9fd5dc2885d00918945f3515c93c": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_wfs_polarity_two_port.v1",
        "reason": "Human adjudication: WFS has two independent axial terminals; internal +/- circles are polarity marks, not ports, and never form a union.",
    },
    "caa4208736b6d031fc40a75f35313c43fc15772b968bedf020c375d6513b0623": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: ELXAL5-B11-209B circular 2x2 contacts 11/12/13/14 are independent outward terminals.",
    },
    "e91786a7f050ea734a00954f590f270c02b054bef7deb7a17b4dab3354cfeaac": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Independent audit provenance for the same-named ELXAL5-B11-209B ellipse-contact geometry; four labelled terminals remain isolated.",
    },
    # Switch-class whole-symbol IGNORE provenance.  The corpus export only
    # retains the stable leading digest here; geometry matching below is never
    # keyed by these values.
    **{
        fp: {"mode": "IGNORE_ELECTRICAL", "family_id": "electrical.nonconnective_switch_class_ignore.v1",
             "reason": "Human adjudication: whole switch-class artwork is provenance-only and emits zero electrical semantics."}
        for fp in (
            "b2289947da2d", "1155e3217907",
            "b143d5dd59ba", "89795189491b", "1b189728ef7b", "54ce0e78a721",
        )
    },
    **{
        fp: {
            "mode": "IGNORE_ELECTRICAL",
            "family_id": "electrical.ground_symbol_ignored.v1",
            "reason": "Human adjudication: PWF166 is a grounding structure; ignore the complete geometry and emit zero ports, mappings, connectivity, or union.",
        }
        for fp in ("5a5823aaf90c", "f3a5a2facd36")
    },
    # Closed cable/sheath capsule crossing B+/B-: visual grouping only.  It
    # neither bridges nor interrupts the underlying conductors and has no
    # relationship to the separately drawn shielding-layer route.
    "2c4f73274833c1b08e7320666b993c4bd5d3e1eedc7a3931b4075e334b8ec1f7": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.cable_sleeve_ignored.v1",
        "reason": "Human adjudication: ignore the closed cable sleeve; B+ and B- remain separate continuous routes, with no shielding-layer mapping.",
    },
    # Grounded three-row LVS-CB assembly: the complete parent, including all
    # nested row mechanisms, common rail, leads, contacts, and ground glyph,
    # is non-mapping artwork for this audit model.
    "346f8b01c9cf292256cf0fecbd3c680e5e79471cfe21420fb1a2d311ed20007e": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete LVS-CB assembly; emit no mappings, external attachments, internal connectivity, or union.",
    },
    # KK1P vertical two-port box: native pins 1/2 map only to their respective
    # same-side external endpoints; the body never joins the two rows.
    "9321616869d2ccca1d1d6fc065a9a995ddf9d31ac8e207430b8eec6439e8ad6b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: compose the instance name with pins 1/2 and map each only to its same-side external endpoint with no internal union.",
    },
    # PWF176 two-contact mechanism: 13 and 14 are independent component
    # terminals.  The drawn switch/actuator body never conducts between them;
    # each side maps only to its own outward lead.
    "8ffdfeebc545ed07bf9b740146cf2c8c729557b453649d679f18248d228d308e": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: 1FA-13 and 1FA-14 are permanently isolated and each maps only to its own outward lead; confirmed 1FA-13 -> 1QD3.",
    },
    # Inline indicator graphic on the P003 switch page: the complete body is
    # annotation-only for this audit model and contributes no electrical map.
    "ea02de2d3b540c5240d289e863160289db7a720c8b7c9db2efbc52c321e45df6": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_inline_indicator_ignored.v1",
        "reason": "Human adjudication: ignore the complete inline indicator; emit no ports, mappings, connectivity, or union.",
    },
    # PWF24a circle/contact marker: the complete vertical graphic is visual
    # equipment annotation and contributes no port or mapping semantics.
    "a662de3d914d6b22aa1b0d6f9e4a0a090de1e0cd8461224860fc8199cba2bf0f": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_circle_contact_marker_ignored.v1",
        "reason": "Human adjudication: ignore the complete circle/contact marker; emit no ports, mappings, connectivity, or union.",
    },
    # PWF182 crossed-circle marker: the two closed side regions and the X
    # inside the circle are recognition geometry only.  Neither side is an
    # electrical port and the complete block must never create a union.
    "de637c582be8e821b1cead5224227ebf5bbfc30d10f68ca7a36f9d20a3295526": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_crossed_circle_marker_ignored.v1",
        "reason": "Human adjudication: ignore the complete crossed-circle marker; its left and right sides are internally disconnected and emit no ports or mappings.",
    },
    # PWF192 actuated open switch: the complete switch drawing is excluded
    # from electrical mapping.  Its two contact regions are not ports and the
    # open blade must never create internal conductivity or a network union.
    "994da514414fa6239674d36dfc616a87430a5dafbab56f009f77b04469580830": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_actuated_open_switch_ignored.v1",
        "reason": "Human adjudication: ignore the complete actuated open-switch drawing; emit no ports, mappings, connectivity, or union.",
    },
    # PWF10 wide contact/cap marker: both polylines are display and selection
    # geometry only.  The complete motif has no electrical port or mapping.
    "25548c2e6081ebe78ea8777dd91b07d6d3f4114392d2c3dcebf79cb16b454f53": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_wide_contact_cap_marker_ignored.v1",
        "reason": "Human adjudication: ignore the complete wide two-contact/cap marker; emit no ports, mappings, connectivity, or union.",
    },
    # A$C1DEA74F8 narrow framed zigzag element: the complete four-cell motif,
    # including both axial leads, is display geometry only.  The fingerprint
    # records provenance; unseen members must satisfy the complete relative
    # geometry matcher below.
    "0b72b0b02116d00c0a8c196e1b45c6d693450315f37e77ba636c0a03065f3785": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_vertical_zigzag_element_ignored.v1",
        "reason": "Human adjudication: ignore the complete narrow four-cell zigzag element; its top and bottom are not ports and create no mappings, connectivity, or union.",
    },
    # PWF168 inline rectangular/contact motif: the complete body and both
    # visible leads are display-only.  The exact member records provenance;
    # unseen members must satisfy the complete relative-geometry matcher.
    "58325f4a6ffb9006fdc46932ed083f730a023c9911ca61a77f042e4d221aa4f3": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_inline_rectangle_ignored.v1",
        "reason": "Human adjudication: ignore the complete PWF168 inline rectangular element; neither side is a port and no mapping, connectivity, or union is allowed.",
    },
    # PWF209 paired-row circular-arc motif: all four outward contacts and arcs
    # are recognition geometry only and must never create port mappings.
    "7cd4cc6f10f5cefc9449d9bad616716bead674add1b076395eb8c7074736bdef": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_dual_row_arc_motif_ignored.v1",
        "reason": "Human adjudication: ignore the complete two-row four-arc motif; emit no ports, mappings, connectivity, or union.",
    },
    # PWF163 is a four-contact actuator variant of the repeatedly reviewed
    # open-switch class.  Its leads and blade remain internally disconnected.
    "dc5a2723a8eaa25d868864a6cb09f5ad614a9901030377377fd96fd91ce476d2": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Inherited human adjudication: ignore the complete PWF163 open-switch variant; zero ports, mappings, connectivity, and union.",
    },
    # PWF175: the two outer contacts are independent native pins 1/2.  The
    # upper page text supplies the instance name; the two circles never bridge.
    "2d7264d385f5a79a1fa9db916f60455ebc62efa8689c86b72bd0e2dbdd929430": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: compose the upper instance name with PWF175 pins 1/2 and map each only to its same-side external route; never connect or union the pins internally.",
    },
    # Phase 166 historical-terminal self-iteration.  These digests preserve
    # provenance only; the independent complete-geometry rules below decide
    # whether renamed/rotated/scaled definitions belong to the same subtype.
    "35ebe7534d569b1e75d8016e963544f5eab546d29d384e20a8c11aff09edefd0": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Inherited basic-terminal adjudication: four orthogonal ports attach only to their own outward routes and never connect or union inside the circular body.",
    },
    "46df2d5ff871f4207483a87594c901f215449957a014bc2340a645652a9b6e17": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Inherited basic two-port adjudication: the two axial contacts remain isolated and attach only to their own outward routes.",
    },
    "f546829e5549f7d19e750599f1de730ecce75b25013b16bf84aa5d7128eaf1cf": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Inherited external-component adjudication: the framed mechanism exposes two isolated axial ports with no internal connectivity or union.",
    },
    "950e83635989de18fe867949c94244cc9691c906cec4f1e5a7126200211bb8fc": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Inherited external-component adjudication: the triangular-body component exposes two isolated axial ports with no internal connectivity or union.",
    },
    "6499eee70c50f91b0fff9ea9b5cd5f4a56b0408c8449d22aaa1e70227107148b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_switch_class_ignore.v1",
        "reason": "Inherited switch/mechanism adjudication: ignore the complete rectangular diagonal mechanism; bbox corners are not ports and no mapping, connectivity, or union is emitted.",
    },
    "2cb256d538072de58edbd7e96d7b9de5bf10efa545d16911bccaab097a84ff1b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.remote_interface_marker_ignored.v1",
        "reason": "Inherited communication-interface adjudication: the RX/TX remote-interface marker is complete non-mapping artwork with zero ports or connectivity.",
    },
    "3a0ce1a5ae19c0fb0ba2fb05202fac2ebfaf64461072fd917b89944a7f020439": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.optical_st_port_ignored.v1",
        "reason": "Inherited ST optical-port adjudication: ignore the complete RX/ST bracket-contact marker and emit no communication mapping.",
    },
    **{
        fp: {
            "mode": "IGNORE_ELECTRICAL",
            "family_id": "line_break.non_connective.v1",
            "reason": "Inherited crossover/line-break adjudication: the closed two-arc/two-line capsule is routing artwork and emits no ports, bridge, mapping, connectivity, or union.",
        }
        for fp in (
            "df872c756ac0caa076adae02142b0cc0084d9a237795b77e0365c552084d1989",
            "0442bf65f378165eec401c8661c82bb3c75749ce517494fc785296917ee0016a",
        )
    },
    # A$C38910F98 is one non-connective panel-internal span.  This exception is
    # deliberately exact: a one-LINE geometry rule would suppress valid wires
    # and the distinct vertical framework member observed in the same corpus.
    "cd0346ad16ba285a9950c48c0611017efcd9490cc6d6d78c81442860902a75cf": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.panel_internal_line.v1",
        "reason": "Human adjudication: exact panel-internal line artifact; ignore the complete span and do not connect its left and right endpoints.",
    },
    # A$C72EB63F1 is physically a panel common bus, but that bus and its branch
    # connectivity are explicitly outside the current audit contract.  Keep
    # this exact so ordinary vertical conductors remain eligible for topology.
    "ae788d00fab7abcd6190c917d8f4c42e8613320b78143443b3849d7e9aea6e72": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.panel_internal_bus_excluded.v1",
        "reason": "Human adjudication: exact panel common bus is excluded from this audit; emit no endpoints, branch mappings, connectivity, or union despite its physical bus semantics.",
    },
    # LA38 four-contact unit: 11/12/13/14 are four independent external
    # component ports; the drawn mechanism never grants port-to-port union.
    "5b68b544d3f7834a0b52c64fa69de4c3a0a64ed859e6c95e11957707e1151eeb": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: 5FA-11/12/13/14 are four mutually isolated ports and each maps only to its own outward lead.",
    },
    # Dual-row hatched signal graphic: all machine extrema are visual-only;
    # the complete component has no external mapping or conductive meaning.
    "c983989529487b8e3894fc9dfc0d0acab9c04fe6a66161f36b695e5c80571396": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_dual_row_signal_panel_ignored.v1",
        "reason": "Human adjudication: all four candidates are unattached visual extrema; ignore the complete dual-row component.",
    },
    # A single repeated row mechanism contributes one named component port.
    # When nested inside the reviewed A' two-row box, the parent owns the
    # resulting A'-1/A'-2 mappings and the child must not emit duplicates.
    "b440ea59c6edcaa2edd135cbfd3ca4d54f80bb2ea554a9ec7af3eeba5a6be3d0": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_row_contact.v1",
        "reason": "Human adjudication: repeated row mechanism inherits the nearby/parent component name and row pin; each row maps only to its own same-side line with no internal union.",
    },
    # A' two-row box: each numbered row maps only to its own external line;
    # no relationship between rows 1 and 2 is inferred.
    "55c2e04f990b264e93b235f7ed3c078a6034a853b3201192f447e7b346d8f06d": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: A'-1 and A'-2 map to their respective upper/lower lines with no internal union.",
    },
    # Repeated HVS-CB coil/panel graphic: visual equipment representation only;
    # no port, mapping, or body connectivity is electrically meaningful.
    "59cf96d51fc55afa4f77a383e0ecf990270dbafbbcd454943b3473039f1a9e5b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_repeated_coil_panel_ignored.v1",
        "reason": "Human adjudication: complete repeated HVS-CB coil panel has no mapping meaning and is electrically ignored.",
    },
    # A jump is wire geometry, not a component and not an IGNORE.  Symbol
    # ports are suppressed here; continuity/no-junction is owned by topology.
    "f9d454c009fff6e62f248535070beb3ce1787db373d260f7159948192c492bb8": {
        "mode": "WIRE_PRIMITIVE",
        "family_id": "wire.crossover_jump.v1",
        "reason": "Human adjudication: LINE-ARC-LINE wire crossover jump; its own path continues and the crossed conductor does not junction.",
    },
    # AK two-port mechanism: each numbered port attaches only to its own
    # external line; the body never creates a 1-2 conductive union.
    "eec06b5aa9987f50b15e7871e0545c46d26b47ec64abdf9ff796d67c2e328bee": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: AK-1 and AK-2 map to their respective external lines with no internal connectivity.",
    },
    # Three-lead boxed graphic: the visible leads do not map through the body
    # and no electrical semantics survive the human adjudication.
    "4f4abeddea8e309da9df83614ee3def2228b9e72a1f9a6e788b270ab13ec8fa1": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_three_lead_box_ignored.v1",
        "reason": "Human adjudication: three-lead boxed graphic is internally disconnected and has no external mapping meaning.",
    },
    # Compact right-side DZB marker: drawing aid only; no port, mapping, or
    # conductive path survives the human adjudication.
    "08a272799dbac4bf36f36ebcc1091f94b2273cf27fce8741a3cf31b150d5d123": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_dzb_right_marker_ignored.v1",
        "reason": "Human adjudication: right-side DZB marker has no connectivity or external mapping.",
    },
    # Four-coil graphic: no external mapping and no conductive path.
    "ea5558fa7d8135a37f959d31a760327230b12ac52509307fec60274eb25768be": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_four_coil_ignored.v1",
        "reason": "Human adjudication: four-coil graphic has no connectivity or external mapping.",
    },
    # WTX-871: the panel is a container; repeated COM/CAN pin cells map
    # independently to external endpoints and never union through the body.
    "7248c0ad77ce6f3a36201f048652a9a63b49fa66a6541b1eb481ad44da886dd7": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_communication_panel.v1",
        "reason": "Human adjudication: communication panel; map repeated COM/CAN pin cells outward, with no internal connectivity.",
    },
    # KNS2500 communication equipment panel: all visible connector and power
    # annotations are non-mapping graphics for this audit model.
    "324c61d3d720cd06224bf81112169aa8a8cfdb5197a715181e376ea2cedfb2a5": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: whole communication-equipment panel is non-connective and creates no external mappings.",
    },
    # DGICOM4000 wide switch panel: every GE/GX/Console/power/ground motif is
    # equipment-face artwork for this audit and creates no mapping of any kind.
    "9ab7144823696cf159b562ccd4a64c5801bdf99275c605494d4964302cc04bd1": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete wide switch panel; emit no communication or electrical ports, mappings, connectivity, or union.",
    },
    # Compact DGICOM3000 equipment face: terminal strip, Console, GE1..GE8,
    # GX9/GX10 and optical motifs are all non-mapping panel artwork.
    "cb1abae65b4bcbd19aa91077fe008419f016357d08608f3712496374f8b8d325": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete compact DGICOM equipment panel and every visible connector/power motif.",
    },
    "1c81d2fb3f1f9586ed2b23a0c9be2c64476f8a2dabff713aa1ec5646a481ac81": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete DGICOM3000-4GX8GE-HV face; all GE/GX, Console, power/ground, optical and port-array artwork is provenance-only.",
    },
    "250a8a04cb457ec7e7ce36f593683166b091ddb9339eb4f51ef017f6c310f363": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Inherited whole-equipment-panel adjudication: ignore the complete DGICOM 8G12/8GE communication face and all nested connector graphics.",
    },
    "75436f14b400ab313bfecfe0f5c6814785ae65cadb3f24456b99ebc0363fc5c9": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Inherited whole-equipment-panel adjudication: ignore the complete WYD COM/LAN/USB/VGA/power face and all nested connector graphics.",
    },
    # HYKL dual-row interface face: IN/OUT PE/GND/TX/RX motifs are panel
    # artwork only and create no electrical or communication mapping.
    "1726acf417090ce3ecbf6454bdb8321afb7c0025023b98e82d59a6b1476dd6dd": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete HYKL interface panel and every IN/OUT PE/GND/TX/RX motif.",
    },
    # NGFW4000 firewall face: ETH/USB/Console/optical and power graphics are
    # all non-mapping panel artwork for this audit model.
    "07d8f9b0bc6c61dd003c0d32861f58c0a1babc0be3cee88783f7dcbb4ab63e25": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.equipment_panel_ignored.v1",
        "reason": "Human adjudication: ignore the complete firewall equipment panel and every visible network, optical, USB, Console, and power motif.",
    },
    # WBH-814E backplate: the outer INSERT is a table-routing container.  It
    # has no direct symbol ports; nested populated plugin tables remain active
    # inputs to TableExtractor and must not be discarded as drawing metadata.
    "5299555132e52b11b5e4f3384c25f7e02a75673bd35ac5e632bceb33dcc9c2a5": {
        "mode": "TABLE_CONTAINER_NO_DIRECT_PORTS",
        "family_id": "structural.backplate_table_container.v1",
        "reason": "Human adjudication: backplate table container; suppress outer pseudo-ports while preserving nested terminal-table mappings.",
    },
    # KK3P: six independent external ports; instance-name + slot number forms
    # the logical endpoint and no body-internal path may be inferred.
    "d5145e5846af5551739c9d3ad82699369c777651188a5b954725d414447dc42b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: KK3P six-port external mapping; no internal connectivity.",
    },
    # KK2P: four independent external ports; the body is not a conductive
    # bridge.  This exact member is retained even when older cached geometry
    # lacks the newer topology evidence.
    "3f7ef8a0ca8b88180e8cf7094e95355e6b2837e7e598cba3a19ce04e6445620a": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: KK2P four-port external mapping; no internal connectivity.",
    },
    # PWF318: grounding glyph is a visual termination marker, not a net port.
    "a6c74f98075e063d0bd026cee40d021e30ded7fb6eabca346385d81d1f8f81e7": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.ground_symbol_ignored.v1",
        "reason": "Human adjudication: ground symbol; zero ports, mappings, and electrical union.",
    },
    "d2978aaddce462eeea764d8295a059d646b00da794aeab718a568e6470bbf56b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.ground_symbol_ignored.v1",
        "reason": "Human adjudication: Ld_DzbJD_Left repeated-line/stepped ground symbol; preserve CAD provenance only, with zero ports, attachments, mappings, pairs, networks, bridges, or union.",
    },
    "3f6efff7be570587c2e273a3f6755e21ff1e0b2036eec28ab5b07b5581e40a1e": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.ground_symbol_ignored.v1",
        "reason": "Human adjudication: PWF4 GND contact-led stepped ground symbol; zero ports, mappings, connectivity, and union.",
    },
    # PWF314: circled ground termination.  The fingerprint records the exact
    # reviewed member; unseen members are accepted only by the independent
    # relative-geometry rule below.
    "1ee219a2138f046ca744c25611726492fb54b31ef2126f57af79a85f66adb36a": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.ground_symbol_ignored.v1",
        "reason": "Inherited ground-symbol adjudication: circled stepped-bar ground marker; zero ports, mappings, connectivity, and union.",
    },
    # Numeric/text block; not an electrical symbol.
    "39b95b5118323d4d8ec235cb43fb72f9b99c8d90ce9f4b2027ee2bdda6255ed5": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.numeric_text.v1",
        "reason": "Human adjudication: numeric/text block, not an electrical symbol.",
    },
    # Graphical symbols that must not create electrical ports or bridges.
    "9a1c6d15833092f32027442d19bd52f5f384395b0bb113e252e5bfbfe66cb85b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.diode_symbol_ignored.v1",
        "reason": "Human adjudication: boxed diode graphic; zero ports, mappings, and electrical union.",
    },
    "765aa9ba366baffab5550e90512b94fb6bc312a9866af101fe7e9ae6571d1c02": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.diode_symbol_ignored.v1",
        "reason": "Human adjudication: bare diode graphic; zero ports, mappings, and electrical union.",
    },
    "a78b06f3c9ab76dc9d36aeecdecb3a32599dbbc55c0e186dbecce76a9ecc780b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "634756a0bafe88dd763d740c97fe13dbbd65921586360b6f96a87d2dc2a408f4": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "8f7479379424184442b346891c2040fe047a8756561435f42095f4e088b39cf1": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Human adjudication: X-marked two-contact switch is ignored; its contacts are internally disconnected and create no mappings.",
    },
    "b37828da29525da55540cc801a451c80b23b3b44b19cd00b7680ddfe1771f746": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.functional_graphic.v1",
        "reason": "Human adjudication: functional conversion symbol, not part of wire connectivity.",
    },
    "cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.equipment_graphic.v1",
        "reason": "Human adjudication: non-connective device graphic in the left-side equipment area.",
    },
    "ef9845390ad82463e1efac6f04551d65d189a6d9a311ce8c2b1398021e70c7cc": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.placeholder.v1",
        "reason": "Human adjudication: no actual electrical meaning.",
    },
    "4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "line_break.non_connective.v1",
        "reason": "Human adjudication: line-break/omission symbol; its sides are disconnected.",
    },
    "b5cc87f72424ca9b4ba46d97f97872e74f1c6f174334905b3ed05bd2d1cc73f0": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.ethernet_port_ignored.v1",
        "reason": "Human adjudication: Ethernet communication port component; do not create external communication mappings.",
    },
    # PWF330: complete Ethernet/LAN port component; the whole block is
    # non-connective, including its visible ETHER/NET label and LAN socket.
    "b65e304c63f2661098d380605c4000e75855fbfcc57985109fad3a21c1c88ed5": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.ethernet_port_ignored.v1",
        "reason": "Human adjudication: complete Ethernet/LAN port component; zero ports, mappings, attachments, internal connectivity, and union.",
    },
    "32f327c96740e2b52598d08b894a9071d6fbeff2f5404d1e81addf7e5ce741db": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "communication.optical_st_port_ignored.v1",
        "reason": "Human adjudication: ST single-mode optical communication port; do not create 1T/1R mappings.",
    },
    # KLP has independently useful external ports but no conductive path
    # through the body. Each port is bound to its own adjacent wire only.
    "61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_inline_two_port.v1",
        "reason": "Human adjudication: KLP ports attach to adjacent external wires only.",
    },
    "2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "5f5573087fee9f48a503ecdede638903fcb979dd5031aaf1e98e69d07f2707f8": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "03db302eda788e4107a4dc2e882e6da52af3d56ea388d8a8f5789e6892a52211": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "cce15b281bc0c0ef0df95453bffcd991d28e73e7683a513b4c3e5f979c243438": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "c578f4c57480a4eabf4f0affb3ac93a9ca7e3eef23ca67e810605b48f06ac99b": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "8f7c185510e495dc79d94bdba73c1335ef0c64043045c388d16d039c52a0fc73": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: slash-circle generic terminal; preserve both external attachments but never connect them internally.",
    },
    "9816226eb2abd1a692ea1af2ef528f5543dbfc10c8ca7d893de0692739019c6b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: three independent E/L/N socket ports; compose outer instance name with each pin and map only to its own external network.",
    },
    "deade9985bacdcfe78b87b08ce5dbb3b05a31ce41bc57086075826fe52baa56f": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: four isolated KZKK ports; map each port only to its same-side external endpoint and never infer switch connectivity.",
    },
    # CD-WSK-H-J-G eight-port unit: the round tag above the body supplies the
    # instance name.  Pins 1..8 attach only to their own outward routes and
    # the complete equipment body never creates pin-to-pin conductivity.
    "d1202915a0dee8f65d4024cd3a144cf7de7147bacc5916dc7cd4b0ebad124bda": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: eight isolated CD-WSK ports; compose the upper circular-tag instance name with pins 1..8 and map each pin only to its same-side external route.",
    },
    # JR-01 two-port box: the separate circular tag above the body supplies
    # the instance name.  Pins 1 and 2 point outward independently and never
    # form a conductive path through the two-circle body.
    "4045826f53f309b218e477ae0163c871aa498b1e0f5c11bf377ee81d26820279": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: JR pins 1/2 are internally isolated; compose the upper circular-tag instance name and map JR-1 to K-3 and JR-2 to K-4 on their own outward routes.",
    },
    "b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "69f5c09b9bfe7e7c3c9db62eaa577a51b98801ec22bb366b8d5d2513ae1b247b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: strip two-port component; each port maps to its own external endpoint.",
    },
    "7b3c62fd0a601f3b7706d8b037a34ffb97c3a8d62873073ae5d4f572b1779e4d": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Inherited FJL adjudication: pins 1/2 are independent outer contacts and map only to their same-side external lines.",
    },
    **{
        fp: {
            "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
            "family_id": "component.external_multi_port.v1",
            "reason": "Human adjudication: expose only the numbered main KK ports; suppress OF 11/12/14 and never infer internal connectivity or union.",
        }
        for fp in (
            "aa15401e4833d9384bde3c70078f7c9bb4446f4af69014cc3be45db4872c00d8",
            "19dacae333477f2d0ca46dc246fc45e8fca072f3ced8dc6d18809d2b5e1f3230",
            "df025098789aab19c27b0cb9e12a4d38ed8ca53d7c4f7f5d9902df3da58b21a6",
        )
    },
    "e84d37eab1d5e64b04de0e6aae32137b3ae80676267d6e24e71266aa4b9e7ee9": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: multi-port component; each port maps to its own external endpoint.",
    },
    "835a7dcc7eae596a7b1a600a48f0e579bf800a22b1add1ffbcc44d2ddb95e054": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: multi-port component; each port maps to its own external endpoint.",
    },
    "84868127dc04f2454ab00c79d63b6d4a57792b2f47365725934a88bcf1986d65": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: PWF89 four-contact generic terminal; bind only genuinely outward-contacting sides to the instance designator, never union the four internal sides.",
    },
    "d90b2e162eca1f771f0a9c25935430b414c2f6fab856d8541fcb3b2d31bc165c": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_led_arrow_ignored.v1",
        "reason": "Human adjudication: PWF172 LED/diode arrow is complete visual artwork and emits no ports or connectivity.",
    },
    "e697f93bfd6720da2581051fde9468a82dadd393c4f49ff654f448300192931f": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "electrical.nonconnective_narrow_frame_ignored.v1",
        "reason": "Human adjudication: PWF216 narrow frame and slanted base are complete visual artwork and emit no ports or connectivity.",
    },
    **{
        fp: {
            "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
            "family_id": "component.external_multi_port.v1",
            "reason": "Inherited numbered-component adjudication: every contiguous numbered pin maps only to its own outward route; the complete body has no internal connectivity or electrical union.",
        }
        for fp in (
            "9d9eb9433e270c52492cd6d0b506393a23e2c20e163f36739cf2868ca85003ce",
            "3888263247353d6cae1d83660f34cc2ce4d0a0683caff489ad27d6a8c8dc8c9a",
            "b43b51c32d7c54dbf3208c9e9d36eb3919e0e3da60dc211c23988d95fba5df3a",
            "358eeedf6d6dd01fca61d9d2947d826106d2f5741f65fc3d66721f195ae74fb0",
            "da27104b38567799b0cccfe4ccfcd40f0e6db3e3f7229c7f28bea17f9a03f4ee",
        )
    },
}


def human_symbol_port_policy(fingerprint: str | None) -> dict[str, str] | None:
    """Return an exact-fingerprint human policy, never a name-based guess."""

    if not fingerprint:
        return None
    normalized = str(fingerprint).strip().casefold()
    policy = HUMAN_SYMBOL_PORT_POLICIES.get(normalized)
    if policy is not None:
        return policy
    # Legacy corpus rows may carry a truncated digest.  The WFS/ELXAL
    # adjudications are deliberately excluded: those three fingerprints are
    # exact provenance and never prefix-authorize a decision.
    for prefix, candidate in HUMAN_SYMBOL_PORT_POLICIES.items():
        if candidate.get("family_id") in {
            "component.external_wfs_polarity_two_port.v1",
        }:
            continue
        if len(prefix) >= 12 and normalized.startswith(prefix):
            return candidate
    return None


def apply_human_symbol_policy_to_proposal_row(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach family/policy evidence while preserving exact human overrides."""

    row = dict(proposal)
    policy = human_symbol_port_policy(row.get("definition_fingerprint"))
    family = classify_definition_family(row)
    behavior = evaluate_symbol_behavior(family, reviewed_policy=policy)
    row.update(family)
    row.update(behavior)
    row["internal_connectivity_inferred"] = False
    row["electrical_union_eligible"] = False
    row["critical_issue_eligible"] = False
    if policy is not None:
        row["human_adjudication_mode"] = policy["mode"]
        row["human_adjudication_reason"] = policy["reason"]
    if behavior["suppressed_by_policy"]:
        row["ports"] = []
        row["status"] = (
            "HUMAN_ADJUDICATED_WIRE_PRIMITIVE"
            if policy is not None and policy["mode"] == "WIRE_PRIMITIVE"
            else "GEOMETRY_FAMILY_WIRE_PRIMITIVE"
            if behavior.get("behavior_mode") == "WIRE_PRIMITIVE"
            else "HUMAN_ADJUDICATED_NON_CONNECTIVE"
            if policy is not None and policy["mode"] == "IGNORE_ELECTRICAL"
            else "HUMAN_ADJUDICATED_TABLE_CONTAINER"
            if policy is not None and policy["mode"] == "TABLE_CONTAINER_NO_DIRECT_PORTS"
            else "GEOMETRY_FAMILY_TABLE_CONTAINER"
            if behavior.get("behavior_mode") == "TABLE_CONTAINER"
            else "GEOMETRY_FAMILY_NON_CONNECTIVE"
        )
    return row


def is_high_confidence_terminal_geometry(proposal: Mapping[str, Any]) -> bool:
    """Recognize compact arc-body terminal geometry without using block names.

    Geometry alone is not enough to emit a terminal relation. Callers must also
    bind a structured terminal designator and an external line contact.
    """

    summary = proposal.get("geometry_summary")
    if not isinstance(summary, Mapping):
        return False
    shape = summary.get("shape_features")
    if not isinstance(shape, Mapping):
        return False
    try:
        arc_radii = [float(value) for value in shape.get("arc_radii", [])]
        primitive_count = int(shape.get("primitive_count", 0))
        text_count = int(shape.get("text_count", 0))
        width = float(shape.get("width"))
        height = float(shape.get("height"))
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(arc_radii) != 2 or any(radius <= 0.0 for radius in arc_radii):
        return False
    mean_radius = sum(arc_radii) / len(arc_radii)
    radius_spread = max(arc_radii) - min(arc_radii)
    invariant_size = max(width, height)
    return (
        radius_spread <= mean_radius * 0.05
        and 0.0 < invariant_size / mean_radius <= 5.2
        and primitive_count <= 12
        and text_count == 0
    )


def _is_slash_circle_two_contact_terminal_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a slash-circle generic terminal by relative topology."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count == 2
            and int(histogram.get("LINE", 0)) in {3, 4}
            and int(histogram.get("LWPOLYLINE", 0)) == 2
            and int(histogram.get("CIRCLE", 0)) == 1
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 2
            and len(circles) == 1
            and len(segments) == int(histogram.get("LINE", 0))
        ):
            return False
        contact_centers = [
            (float(item["center"][0]), float(item["center"][1]))
            for item in contacts
        ]
        contact_radii = [float(item["radius"]) for item in contacts]
        circle_center = (
            float(circles[0]["center"][0]),
            float(circles[0]["center"][1]),
        )
        circle_radius = float(circles[0]["radius"])
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    def distance(left, right) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    spacing = distance(contact_centers[0], contact_centers[1])
    if spacing <= 1e-9 or min(contact_radii) <= 1e-9:
        return False
    if max(contact_radii) / min(contact_radii) > 1.05:
        return False
    mean_contact_radius = sum(contact_radii) / 2.0
    if not (2.2 <= circle_radius / mean_contact_radius <= 2.6):
        return False
    axis_x = (contact_centers[1][0] - contact_centers[0][0]) / spacing
    axis_y = (contact_centers[1][1] - contact_centers[0][1]) / spacing
    center_dx = circle_center[0] - contact_centers[0][0]
    center_dy = circle_center[1] - contact_centers[0][1]
    projection = (center_dx * axis_x + center_dy * axis_y) / spacing
    perpendicular = abs(center_dx * axis_y - center_dy * axis_x)
    if not (0.47 <= projection <= 0.53 and perpendicular <= spacing * 0.02):
        return False

    axial: list[tuple[tuple[float, float], tuple[float, float]]] = []
    slash: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for segment in parsed_segments:
        dx = segment[1][0] - segment[0][0]
        dy = segment[1][1] - segment[0][1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        alignment = abs((dx / length) * axis_x + (dy / length) * axis_y)
        (axial if alignment >= 0.95 else slash).append(segment)
    if len(axial) != 2 or len(slash) != 2:
        return False

    used_contacts: set[int] = set()
    for lead in axial:
        nearest = min(
            (
                (distance(endpoint, contact), endpoint_index, contact_index)
                for endpoint_index, endpoint in enumerate(lead)
                for contact_index, contact in enumerate(contact_centers)
            ),
            key=lambda item: item[0],
        )
        if nearest[0] > spacing * 0.02 or nearest[2] in used_contacts:
            return False
        used_contacts.add(nearest[2])
        inner = lead[1 - nearest[1]]
        if abs(distance(inner, circle_center) - circle_radius) > circle_radius * 0.08:
            return False
    if used_contacts != {0, 1}:
        return False

    shared = min(
        (
            (distance(left, right), left_index, right_index)
            for left_index, left in enumerate(slash[0])
            for right_index, right in enumerate(slash[1])
        ),
        key=lambda item: item[0],
    )
    if shared[0] > spacing * 0.02:
        return False
    shared_point = slash[0][shared[1]]
    if distance(shared_point, circle_center) > spacing * 0.02:
        return False
    outer = (slash[0][1 - shared[1]], slash[1][1 - shared[2]])
    outer_vectors = [(point[0] - circle_center[0], point[1] - circle_center[1]) for point in outer]
    outer_distances = [math.hypot(vector[0], vector[1]) for vector in outer_vectors]
    return bool(
        all(1.5 <= value / circle_radius <= 1.8 for value in outer_distances)
        and (outer_vectors[0][0] * outer_vectors[1][0] + outer_vectors[0][1] * outer_vectors[1][1])
        / (outer_distances[0] * outer_distances[1]) <= -0.98
    )


def _is_four_contact_terminal_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the four-way slash-circle state of a generic terminal."""
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if (
            port_count != 4
            or int(histogram.get("LINE", 0)) != 5
            or int(histogram.get("LWPOLYLINE", 0)) != 4
            or int(histogram.get("CIRCLE", 0)) != 1
            or int(histogram.get("TEXT", 0)) != 0
            or int(histogram.get("MTEXT", 0)) != 0
            or len(contacts) != 4
            or len(circles) != 1
            or len(segments) != 5
        ):
            return False
        points = [
            (float(contact["center"][0]), float(contact["center"][1]))
            for contact in contacts
        ]
        radii = [float(contact["radius"]) for contact in contacts]
        center = (float(circles[0]["center"][0]), float(circles[0]["center"][1]))
        circle_r = float(circles[0]["radius"])
        lines = [
            (
                (float(segment["start"][0]), float(segment["start"][1])),
                (float(segment["end"][0]), float(segment["end"][1])),
            )
            for segment in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    if (
        min(radii) <= 1e-9
        or circle_r <= 1e-9
        or max(radii) / min(radii) > 1.08
        or not 2.15 <= circle_r / (sum(radii) / len(radii)) <= 2.65
    ):
        return False
    distances = [math.hypot(x - center[0], y - center[1]) for x, y in points]
    if (
        min(distances) <= 1e-9
        or max(distances) / min(distances) > 1.08
        or not 1.9 <= min(distances) / circle_r <= 2.25
    ):
        return False
    vectors = [(x - center[0], y - center[1]) for x, y in points]
    # Every contact has one opposite mate and two perpendicular neighbours.
    for index, vector in enumerate(vectors):
        cosines = sorted(
            (
                (
                    vector[0] * other[0] + vector[1] * other[1]
                )
                / (distances[index] * distances[other_index])
            )
            for other_index, other in enumerate(vectors)
            if other_index != index
        )
        if cosines[0] > -0.96 or any(abs(value) > 0.12 for value in cosines[1:]):
            return False

    radial_tolerance = min(distances) * 0.04
    radial_line_indices: set[int] = set()
    used_contacts: set[int] = set()
    for contact_index, (contact, radial_vector, radial_distance) in enumerate(
        zip(points, vectors, distances)
    ):
        unit = (radial_vector[0] / radial_distance, radial_vector[1] / radial_distance)
        matches: list[int] = []
        for line_index, (start, end) in enumerate(lines):
            start_contact_distance = math.hypot(
                start[0] - contact[0], start[1] - contact[1]
            )
            end_contact_distance = math.hypot(
                end[0] - contact[0], end[1] - contact[1]
            )
            if min(start_contact_distance, end_contact_distance) > radial_tolerance:
                continue
            inner = end if start_contact_distance <= end_contact_distance else start
            inner_vector = (inner[0] - center[0], inner[1] - center[1])
            inner_distance = math.hypot(inner_vector[0], inner_vector[1])
            if inner_distance <= 1e-9:
                continue
            alignment = (
                inner_vector[0] * unit[0] + inner_vector[1] * unit[1]
            ) / inner_distance
            if (
                alignment >= 0.98
                and abs(inner_distance - circle_r) <= circle_r * 0.08
            ):
                matches.append(line_index)
        if len(matches) != 1 or matches[0] in radial_line_indices:
            return False
        radial_line_indices.add(matches[0])
        used_contacts.add(contact_index)
    if len(radial_line_indices) != 4 or len(used_contacts) != 4:
        return False

    # The remaining line must be the centred slash, not an arbitrary fifth line.
    slash_indices = set(range(len(lines))) - radial_line_indices
    if len(slash_indices) != 1:
        return False
    slash = lines[slash_indices.pop()]
    slash_vectors = [
        (point[0] - center[0], point[1] - center[1]) for point in slash
    ]
    slash_distances = [math.hypot(vector[0], vector[1]) for vector in slash_vectors]
    if min(slash_distances) <= 1e-9 or max(slash_distances) / min(slash_distances) > 1.08:
        return False
    slash_opposition = (
        slash_vectors[0][0] * slash_vectors[1][0]
        + slash_vectors[0][1] * slash_vectors[1][1]
    ) / (slash_distances[0] * slash_distances[1])
    if slash_opposition > -0.98 or not all(
        1.55 <= value / circle_r <= 1.8 for value in slash_distances
    ):
        return False
    slash_unit = (
        slash_vectors[0][0] / slash_distances[0],
        slash_vectors[0][1] / slash_distances[0],
    )
    axis_alignment = max(
        abs(
            slash_unit[0] * vector[0] / radial_distance
            + slash_unit[1] * vector[1] / radial_distance
        )
        for vector, radial_distance in zip(vectors, distances)
    )
    return 0.55 <= axis_alignment <= 0.85


def _is_four_radial_isolated_terminal_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize four independent radial contacts around a plain round body."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count == 4
            and int(histogram.get("CIRCLE", 0)) == 1
            and int(histogram.get("LINE", 0)) in {3, 4}
            and int(histogram.get("LWPOLYLINE", 0)) == 4
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == len(segments) == 4
            and len(circles) == 1
        ):
            return False
        center = tuple(float(value) for value in circles[0]["center"][:2])
        body_radius = float(circles[0]["radius"])
        parsed_contacts = [
            (
                tuple(float(value) for value in item["center"][:2]),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        parsed_segments = [
            (
                tuple(float(value) for value in item["start"][:2]),
                tuple(float(value) for value in item["end"][:2]),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    radii = [radius for _, radius in parsed_contacts]
    contact_radius = sum(radii) / 4.0
    if not (
        contact_radius > 0.0
        and max(radii) - min(radii) <= contact_radius * 0.03
        and 1.95 <= body_radius / contact_radius <= 2.05
    ):
        return False
    vectors = [(point[0] - center[0], point[1] - center[1]) for point, _ in parsed_contacts]
    lengths = [math.hypot(*vector) for vector in vectors]
    if not all(3.95 <= value / contact_radius <= 4.15 for value in lengths):
        return False
    units = [(x / length, y / length) for (x, y), length in zip(vectors, lengths)]
    for index, unit in enumerate(units):
        dots = sorted(
            unit[0] * other[0] + unit[1] * other[1]
            for other_index, other in enumerate(units)
            if other_index != index
        )
        if dots[0] > -0.98 or any(abs(value) > 0.04 for value in dots[1:]):
            return False
    unused = set(range(4))
    for contact, _ in parsed_contacts:
        matches = []
        for index in unused:
            segment = parsed_segments[index]
            nearest = min(
                ((math.dist(endpoint, contact), endpoint_index) for endpoint_index, endpoint in enumerate(segment)),
                key=lambda item: item[0],
            )
            inner = segment[1 - nearest[1]]
            if (
                nearest[0] <= contact_radius * 0.03
                and abs(math.dist(inner, center) - body_radius) <= body_radius * 0.04
            ):
                matches.append(index)
        if len(matches) != 1:
            return False
        unused.remove(matches[0])
    return not unused


def _is_round_body_isolated_two_port_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize an axial two-contact round body without granting a bridge."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count == 2
            and int(histogram.get("CIRCLE", 0)) == 1
            and int(histogram.get("HATCH", 0)) == 1
            and int(histogram.get("LINE", 0)) == 3
            and int(histogram.get("LWPOLYLINE", 0)) == 2
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 2
            and len(circles) == 1
            and len(segments) == 3
        ):
            return False
        points = [tuple(float(value) for value in item["center"][:2]) for item in contacts]
        radii = [float(item.get("chord_radius") or item["radius"]) for item in contacts]
        center = tuple(float(value) for value in circles[0]["center"][:2])
        body_radius = float(circles[0]["radius"])
        lines = [
            (
                tuple(float(value) for value in item["start"][:2]),
                tuple(float(value) for value in item["end"][:2]),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    contact_radius = sum(radii) / 2.0
    span = math.dist(*points)
    midpoint = ((points[0][0] + points[1][0]) / 2.0, (points[0][1] + points[1][1]) / 2.0)
    if not (
        contact_radius > 0.0
        and abs(radii[0] - radii[1]) <= contact_radius * 0.02
        and math.dist(midpoint, center) <= span * 0.01
        and 1.95 <= body_radius / contact_radius <= 2.05
        and 4.95 <= span / body_radius <= 5.05
    ):
        return False
    axis = ((points[1][0] - points[0][0]) / span, (points[1][1] - points[0][1]) / span)
    axial_lines = []
    for line in lines:
        vector = (line[1][0] - line[0][0], line[1][1] - line[0][1])
        length = math.hypot(*vector)
        if length <= 0.0 or abs(vector[0] * axis[0] + vector[1] * axis[1]) / length < 0.995:
            return False
        axial_lines.append((length, line))
    axial_lines.sort(key=lambda item: item[0])
    # Two equal outer leads plus one centred body span are all required.
    if abs(axial_lines[0][0] - axial_lines[1][0]) > span * 0.01:
        return False
    long_line = axial_lines[2][1]
    long_midpoint = (
        (long_line[0][0] + long_line[1][0]) / 2.0,
        (long_line[0][1] + long_line[1][1]) / 2.0,
    )
    if math.dist(long_midpoint, center) > span * 0.01:
        return False
    used: set[int] = set()
    for contact in points:
        candidates = []
        for index, (_, line) in enumerate(axial_lines[:2]):
            candidates.append(min(math.dist(contact, line[0]), math.dist(contact, line[1])))
        match = min(range(2), key=lambda index: candidates[index])
        if candidates[match] > span * 0.01 or match in used:
            return False
        used.add(match)
    return used == {0, 1}


def _is_dual_frame_isolated_two_port_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the two-box/four-line axial mechanism used by PWF218."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    boxes = shape.get("normalized_closed_straight_lwpolylines") or []
    try:
        if not (
            port_count == 2
            and int(histogram.get("LINE", 0)) == 4
            and int(histogram.get("LWPOLYLINE", 0)) == 4
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 2
            and len(segments) == int(histogram.get("LINE", 0))
            and len(boxes) == 2
        ):
            return False
        points = [tuple(float(value) for value in item["center"][:2]) for item in contacts]
        radii = [float(item.get("chord_radius") or item["radius"]) for item in contacts]
        lines = [
            (
                tuple(float(value) for value in item["start"][:2]),
                tuple(float(value) for value in item["end"][:2]),
            )
            for item in segments
        ]
        box_sizes = [(float(item["width"]), float(item["height"])) for item in boxes]
        box_centers = [tuple(float(value) for value in item["center"][:2]) for item in boxes]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    span = math.dist(*points)
    radius = sum(radii) / 2.0
    lengths = sorted(math.dist(*line) for line in lines)
    if not (
        span > 0.0
        and radius > 0.0
        and abs(radii[0] - radii[1]) <= radius * 0.02
        and 22.0 <= span / radius <= 23.0
        and lengths[-1] / lengths[0] <= 1.08
        and abs(box_sizes[0][0] - box_sizes[1][0]) <= span * 0.01
    ):
        return False
    contact_bound_lines = 0
    for point in points:
        matches = [line for line in lines if min(math.dist(point, line[0]), math.dist(point, line[1])) <= span * 0.01]
        if len(matches) != 1:
            return False
        contact_bound_lines += 1
    if contact_bound_lines != 2:
        return False
    midpoint = (
        (points[0][0] + points[1][0]) / 2.0,
        (points[0][1] + points[1][1]) / 2.0,
    )
    axis = (
        (points[1][0] - points[0][0]) / span,
        (points[1][1] - points[0][1]) / span,
    )
    if any(
        abs((center[0] - midpoint[0]) * axis[0] + (center[1] - midpoint[1]) * axis[1])
        > span * 0.02
        for center in box_centers
    ):
        return False
    center_gap = math.dist(*box_centers)
    tall = max(max(size) for size in box_sizes)
    short = min(min(size) for size in box_sizes)
    return 0.42 <= center_gap / span <= 0.48 and 0.64 <= tall / span <= 0.70 and 0.25 <= short / span <= 0.36


def _is_triangle_body_isolated_two_port_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize two axial contacts with one centred triangular body."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    polygons = shape.get("normalized_closed_straight_lwpolylines") or []
    try:
        if not (
            port_count == 2
            and int(histogram.get("LINE", 0)) == 1
            and int(histogram.get("LWPOLYLINE", 0)) == 3
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 2
            and len(segments) == 1
            and len(polygons) == 1
            and len(polygons[0].get("vertices") or []) == 3
        ):
            return False
        points = [tuple(float(value) for value in item["center"][:2]) for item in contacts]
        radii = [float(item.get("chord_radius") or item["radius"]) for item in contacts]
        line = (
            tuple(float(value) for value in segments[0]["start"][:2]),
            tuple(float(value) for value in segments[0]["end"][:2]),
        )
        polygon = polygons[0]
        vertices = [tuple(float(value) for value in vertex[:2]) for vertex in polygon["vertices"]]
        width = float(polygon["width"])
        height = float(polygon["height"])
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    span = math.dist(*points)
    radius = sum(radii) / 2.0
    if not (
        span > 0.0
        and abs(radii[0] - radii[1]) <= radius * 0.02
        and 19.5 <= span / radius <= 20.5
        and abs(math.dist(*line) - span) <= span * 0.01
        and all(min(math.dist(point, line[0]), math.dist(point, line[1])) <= span * 0.01 for point in points)
        and 0.25 <= min(width, height) / span <= 0.32
        and 0.25 <= max(width, height) / span <= 0.32
    ):
        return False
    axis = ((points[1][0] - points[0][0]) / span, (points[1][1] - points[0][1]) / span)
    projections = sorted(((vertex[0] - points[0][0]) * axis[0] + (vertex[1] - points[0][1]) * axis[1]) / span for vertex in vertices)
    normal = (-axis[1], axis[0])
    perpendiculars = sorted(
        ((vertex[0] - points[0][0]) * normal[0] + (vertex[1] - points[0][1]) * normal[1]) / span
        for vertex in vertices
    )
    return bool(
        0.40 <= projections[0] <= 0.43
        and 0.66 <= projections[-1] <= 0.69
        and -0.16 <= perpendiculars[0] <= -0.14
        and abs(perpendiculars[1]) <= 0.01
        and 0.14 <= perpendiculars[2] <= 0.16
    )


def _is_rectangular_diagonal_mechanism_ignore_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a square/diagonal mechanism whose bbox corners are not ports."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    boxes = shape.get("normalized_closed_straight_lwpolylines") or []
    try:
        if not (
            port_count in {0, 4}
            and int(histogram.get("LINE", 0)) == 1
            and int(histogram.get("LWPOLYLINE", 0)) == 3
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 2
            and len(segments) == 1
            and len(boxes) == 1
            and len(boxes[0].get("vertices") or []) == 4
        ):
            return False
        points = [tuple(float(value) for value in item["center"][:2]) for item in contacts]
        radii = [float(item.get("chord_radius") or item["radius"]) for item in contacts]
        line = (
            tuple(float(value) for value in segments[0]["start"][:2]),
            tuple(float(value) for value in segments[0]["end"][:2]),
        )
        box = boxes[0]
        vertices = [tuple(float(value) for value in vertex[:2]) for vertex in box["vertices"]]
        width, height = float(box["width"]), float(box["height"])
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    edge = (width + height) / 2.0
    radius = sum(radii) / 2.0
    if not (
        edge > 0.0
        and abs(width - height) <= edge * 0.02
        and abs(radii[0] - radii[1]) <= radius * 0.02
        and 24.5 <= edge / radius <= 25.5
        and 1.40 <= math.dist(*line) / edge <= 1.43
    ):
        return False
    # The only line is a box diagonal, while both contacts sit on one other
    # box edge inset by one contact radius.  This rejects ordinary rectangles.
    if not all(min(math.dist(endpoint, vertex) for vertex in vertices) <= edge * 0.01 for endpoint in line):
        return False
    pair_distance = math.dist(*points)
    distances_to_edges = []
    for index in range(4):
        start, end = vertices[index], vertices[(index + 1) % 4]
        length = math.dist(start, end)
        if length <= 0.0:
            continue
        distances_to_edges.append(
            max(_point_segment_distance(point, start, end) for point in points)
        )
    return 0.78 <= pair_distance / edge <= 0.82 and min(distances_to_edges, default=edge) <= edge * 0.01


def _is_remote_interface_marker_ignore_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a contact-led round remote-interface marker with a centre slash."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count in {0, 3}
            and int(histogram.get("CIRCLE", 0)) == 1
            and int(histogram.get("LINE", 0)) == 2
            and int(histogram.get("LWPOLYLINE", 0)) == 1
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == len(circles) == 1
            and len(segments) == 2
        ):
            return False
        contact = tuple(float(value) for value in contacts[0]["center"][:2])
        contact_radius = float(contacts[0].get("chord_radius") or contacts[0]["radius"])
        center = tuple(float(value) for value in circles[0]["center"][:2])
        body_radius = float(circles[0]["radius"])
        lines = [
            (
                tuple(float(value) for value in item["start"][:2]),
                tuple(float(value) for value in item["end"][:2]),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    spacing = math.dist(contact, center)
    if not (
        contact_radius > 0.0
        and body_radius > 0.0
        and 2.35 <= body_radius / contact_radius <= 2.45
        and 2.05 <= spacing / body_radius <= 2.10
    ):
        return False
    lead_matches = []
    slash_matches = []
    for line in lines:
        endpoint_distances = [math.dist(contact, endpoint) for endpoint in line]
        if min(endpoint_distances) <= contact_radius * 0.03:
            inner = line[1 - endpoint_distances.index(min(endpoint_distances))]
            if abs(math.dist(inner, center) - body_radius) <= body_radius * 0.04:
                lead_matches.append(line)
            continue
        midpoint = ((line[0][0] + line[1][0]) / 2.0, (line[0][1] + line[1][1]) / 2.0)
        endpoints = [math.dist(endpoint, center) for endpoint in line]
        if (
            math.dist(midpoint, center) <= body_radius * 0.03
            and max(endpoints) / min(endpoints) <= 1.03
            and all(1.65 <= value / body_radius <= 1.70 for value in endpoints)
        ):
            slash_matches.append(line)
    return len(lead_matches) == len(slash_matches) == 1


def _is_optical_st_bracket_marker_ignore_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the two-contact parenthesis marker used beside RX/ST labels."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    text_values = [str(value).strip() for value in shape.get("text_values") or []]
    try:
        if not (
            port_count in {0, 3}
            and int(histogram.get("LWPOLYLINE", 0)) == 2
            and int(histogram.get("TEXT", 0)) == 1
            and sum(int(histogram.get(key, 0)) for key in ("LINE", "ARC", "CIRCLE", "INSERT")) == 0
            and len(contacts) == 2
            and text_values == ["（"]
        ):
            return False
        points = [tuple(float(value) for value in item["center"][:2]) for item in contacts]
        radii = [float(item.get("chord_radius") or item["radius"]) for item in contacts]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    radius = sum(radii) / 2.0
    return bool(
        radius > 0.0
        and abs(radii[0] - radii[1]) <= radius * 0.02
        and 7.0 <= math.dist(*points) / radius <= 7.15
    )


def _is_two_arc_capsule_routing_ignore_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a closed capsule made from two parallel lines and semicircles."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    arcs = shape.get("normalized_arcs") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count in {0, 2}
            and int(histogram.get("ARC", 0)) == 2
            and int(histogram.get("LINE", 0)) == 2
            and int(histogram.get("LWPOLYLINE", 0)) == 0
            and int(histogram.get("TEXT", 0)) == 0
            and len(arcs) == len(segments) == 2
        ):
            return False
        lines = [
            (
                tuple(float(value) for value in item["start"][:2]),
                tuple(float(value) for value in item["end"][:2]),
            )
            for item in segments
        ]
        parsed_arcs = [
            (
                tuple(float(value) for value in item["center"][:2]),
                float(item["radius"]),
                float(item["sweep_deg"]),
                tuple(float(value) for value in item["midpoint"][:2]),
            )
            for item in arcs
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    lengths = [math.dist(*line) for line in lines]
    radii = [item[1] for item in parsed_arcs]
    if not (
        min(lengths) > 0.0
        and abs(lengths[0] - lengths[1]) <= max(lengths) * 0.02
        and min(radii) > 0.0
        and abs(radii[0] - radii[1]) <= max(radii) * 0.02
        and all(179.0 <= abs(item[2]) <= 181.0 for item in parsed_arcs)
        and 3.9 <= lengths[0] / (2.0 * radii[0]) <= 4.1
    ):
        return False
    vectors = [(line[1][0] - line[0][0], line[1][1] - line[0][1]) for line in lines]
    alignment = abs(vectors[0][0] * vectors[1][0] + vectors[0][1] * vectors[1][1]) / (lengths[0] * lengths[1])
    if alignment < 0.999:
        return False
    arc_center_span = math.dist(parsed_arcs[0][0], parsed_arcs[1][0])
    cap_width = min(
        math.dist(lines[0][0], lines[1][0]), math.dist(lines[0][0], lines[1][1]),
        math.dist(lines[0][1], lines[1][0]), math.dist(lines[0][1], lines[1][1]),
    )
    return bool(
        3.9 <= arc_center_span / (2.0 * radii[0]) <= 4.1
        and 0.95 <= cap_width / (2.0 * radii[0]) <= 1.05
        and all(abs(math.dist(item[3], item[0]) - item[1]) <= item[1] * 0.02 for item in parsed_arcs)
    )


def _is_rounded_panel_three_contact_socket_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a rounded rectangular E/N/L socket panel.

    This variant has one extra small boundary contact for the internal J1
    mechanism.  Only the three contacts nearest the labelled E/N/L circles
    are external electrical ports.
    """

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
    }
    try:
        if not (
            port_count == 3
            and int(histogram.get("CIRCLE", 0)) == 3
            and 4 <= int(histogram.get("LWPOLYLINE", 0)) <= 8
            and 8 <= int(histogram.get("LINE", 0)) <= 24
            and {"E", "L", "N"}.issubset(values)
            and len(circles) == 3
            and 4 <= len(contacts) <= 8
        ):
            return False
        parsed_circles = [
            ((float(item["center"][0]), float(item["center"][1])), float(item["radius"]))
            for item in circles
        ]
        parsed_contacts = [
            ((float(item["center"][0]), float(item["center"][1])), float(item["radius"]))
            for item in contacts
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    circle_radii = [radius for _, radius in parsed_circles]
    if (
        min(circle_radii) <= 1e-9
        or max(circle_radii) / min(circle_radii) > 1.05
    ):
        return False
    pair_distances = sorted(
        distance(parsed_circles[left][0], parsed_circles[right][0])
        for left in range(3)
        for right in range(left + 1, 3)
    )
    if not (
        pair_distances[0] > max(circle_radii) * 2.5
        and pair_distances[2] / pair_distances[1] <= 1.08
        and 1.5 <= pair_distances[1] / pair_distances[0] <= 2.5
    ):
        return False

    minimum_contact_radius = min(radius for _, radius in parsed_contacts)
    if minimum_contact_radius <= 1e-9:
        return False
    small_contacts = [
        center
        for center, radius in parsed_contacts
        if radius <= minimum_contact_radius * 1.1
    ]
    outline_radii = [
        radius
        for _, radius in parsed_contacts
        if radius >= minimum_contact_radius * 10.0
    ]
    if not (4 <= len(small_contacts) <= 6 and len(outline_radii) == 1):
        return False

    selected_contacts = []
    mean_circle_radius = sum(circle_radii) / len(circle_radii)
    for circle_center, _ in parsed_circles:
        nearest = min(small_contacts, key=lambda contact: distance(circle_center, contact))
        nearest_distance = distance(circle_center, nearest)
        if not (1.5 <= nearest_distance / mean_circle_radius <= 4.5):
            return False
        selected_contacts.append(nearest)
    return len(set(selected_contacts)) == 3


def _is_three_contact_socket_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a three-way socket with independent outer contacts."""

    if _is_rounded_panel_three_contact_socket_geometry(
        shape, port_count=port_count
    ):
        return True

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count in {2, 3}
            and int(histogram.get("LINE", 0)) == 4
            and int(histogram.get("LWPOLYLINE", 0)) == 6
            and int(histogram.get("CIRCLE", 0)) == 4
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 6
            and len(circles) == 4
            and len(segments) == 3
        ):
            return False
        parsed_contacts = [
            ((float(item["center"][0]), float(item["center"][1])), float(item["radius"]))
            for item in contacts
        ]
        parsed_circles = [
            ((float(item["center"][0]), float(item["center"][1])), float(item["radius"]))
            for item in circles
        ]
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    def distance(left, right) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    contact_radii = [radius for _, radius in parsed_contacts]
    if min(contact_radii) <= 1e-9 or max(contact_radii) / min(contact_radii) > 1.05:
        return False
    outer_center, outer_radius = max(parsed_circles, key=lambda item: item[1])
    inner_circles = [item for item in parsed_circles if item[1] < outer_radius]
    if len(inner_circles) != 3 or min(radius for _, radius in inner_circles) <= 1e-9:
        return False
    if max(radius for _, radius in inner_circles) / min(radius for _, radius in inner_circles) > 1.05:
        return False
    if not (2.4 <= outer_radius / (sum(radius for _, radius in inner_circles) / 3.0) <= 2.6):
        return False

    outer_contacts = [
        center
        for center, _ in parsed_contacts
        if 1.45 <= distance(center, outer_center) / outer_radius <= 1.55
    ]
    inner_contacts = [
        center
        for center, _ in parsed_contacts
        if any(distance(center, circle_center) <= outer_radius * 0.02 for circle_center, _ in inner_circles)
    ]
    if len(outer_contacts) != 3 or len(inner_contacts) != 3:
        return False
    farthest_pair = max(
        ((left, right) for left in range(3) for right in range(left + 1, 3)),
        key=lambda pair: distance(outer_contacts[pair[0]], outer_contacts[pair[1]]),
    )
    first, second = (outer_contacts[index] for index in farthest_pair)
    if not (
        2.9 <= distance(first, second) / outer_radius <= 3.1
        and distance(((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0), outer_center)
        <= outer_radius * 0.03
    ):
        return False
    third = next(
        outer_contacts[index]
        for index in range(3)
        if index not in farthest_pair
    )
    pair_axis = (second[0] - first[0], second[1] - first[1])
    third_axis = (third[0] - outer_center[0], third[1] - outer_center[1])
    if abs(pair_axis[0] * third_axis[0] + pair_axis[1] * third_axis[1]) > outer_radius**2 * 0.08:
        return False

    used_contacts: set[int] = set()
    for segment in parsed_segments:
        nearest = min(
            (
                (distance(endpoint, contact), endpoint_index, contact_index)
                for endpoint_index, endpoint in enumerate(segment)
                for contact_index, contact in enumerate(outer_contacts)
            ),
            key=lambda item: item[0],
        )
        if nearest[0] > outer_radius * 0.03 or nearest[2] in used_contacts:
            return False
        used_contacts.add(nearest[2])
        inner = segment[1 - nearest[1]]
        outer = outer_contacts[nearest[2]]
        outward = (outer[0] - outer_center[0], outer[1] - outer_center[1])
        inward = (inner[0] - outer[0], inner[1] - outer[1])
        if outward[0] * inward[0] + outward[1] * inward[1] >= 0.0:
            return False
        if not (0.45 <= distance(inner, outer) / outer_radius <= 0.55):
            return False
    return used_contacts == {0, 1, 2}


def _is_three_contact_selector_switch_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Complete selector-switch artwork: three radial contacts and a slash."""
    histogram = shape.get("entity_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    segments = shape.get("normalized_line_segments") or []
    if not (
        port_count in {0, 4}
        and histogram == {"CIRCLE": 1, "LINE": 4, "LWPOLYLINE": 3}
        and len(contacts) == 3
        and len(circles) == 1
        and len(segments) == 4
        and not (shape.get("text_values") or [])
    ):
        return False
    try:
        center = tuple(float(value) for value in circles[0]["center"][:2])
        body_radius = float(circles[0]["radius"])
        parsed_contacts = [
            (
                tuple(float(value) for value in contact["center"][:2]),
                float(contact.get("chord_radius", contact.get("radius"))),
            )
            for contact in contacts
        ]
        parsed_segments = [
            (
                tuple(float(value) for value in segment["start"][:2]),
                tuple(float(value) for value in segment["end"][:2]),
            )
            for segment in segments
        ]
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    contact_radii = [radius for _, radius in parsed_contacts]
    contact_radius = sum(contact_radii) / 3.0
    if not (
        contact_radius > 0.0
        and max(contact_radii) - min(contact_radii) <= contact_radius * 0.02
        and 2.35 <= body_radius / contact_radius <= 2.45
    ):
        return False
    vectors = [
        ((point[0] - center[0]) / contact_radius, (point[1] - center[1]) / contact_radius)
        for point, _ in parsed_contacts
    ]
    lengths = [math.hypot(*vector) for vector in vectors]
    if not all(4.9 <= length <= 5.1 for length in lengths):
        return False
    units = [(vector[0] / length, vector[1] / length) for vector, length in zip(vectors, lengths)]
    opposite_pair = next(
        (
            (first, second)
            for first, second in combinations(range(3), 2)
            if units[first][0] * units[second][0] + units[first][1] * units[second][1] <= -0.99
        ),
        None,
    )
    if opposite_pair is None:
        return False
    third = next(index for index in range(3) if index not in opposite_pair)
    if abs(
        units[opposite_pair[0]][0] * units[third][0]
        + units[opposite_pair[0]][1] * units[third][1]
    ) > 0.03:
        return False

    used_segments: set[int] = set()
    for contact_center, _ in parsed_contacts:
        match: tuple[float, int, tuple[float, float]] | None = None
        for index, segment in enumerate(parsed_segments):
            if index in used_segments:
                continue
            for endpoint_index, endpoint in enumerate(segment):
                candidate = (
                    math.dist(endpoint, contact_center),
                    index,
                    segment[1 - endpoint_index],
                )
                if match is None or candidate[0] < match[0]:
                    match = candidate
        if match is None or match[0] > contact_radius * 0.02:
            return False
        if not 0.98 <= math.dist(match[2], center) / body_radius <= 1.02:
            return False
        used_segments.add(match[1])
    slash = next((segment for index, segment in enumerate(parsed_segments) if index not in used_segments), None)
    if slash is None or not 7.9 <= math.dist(*slash) / contact_radius <= 8.1:
        return False
    return _point_segment_distance(center, slash[0], slash[1]) <= contact_radius * 0.03


def _actuated_switch_signature_rule(
    shape: Mapping[str, Any], *, port_count: int
) -> str | None:
    """Match three complete actuator/contact subtypes by invariant ratios."""
    templates = (
        (
            {"ARC": 1, "LINE": 5, "LWPOLYLINE": 2}, {0, 3},
            (0.761790, 0.761790, 0.851705, 0.923822, 1.0),
            0.304715, 0.101571, 2.285367,
            "five-line-offset-actuator-switch-ignore-v1",
        ),
        (
            {"ARC": 1, "LINE": 6, "LWPOLYLINE": 2}, {0, 2},
            (0.371390, 0.685364, 0.742783, 0.742783, 0.744787, 1.0),
            0.297113, 0.099037, 2.228346,
            "six-line-double-stem-actuator-switch-ignore-v1",
        ),
        (
            {"ARC": 1, "LINE": 11, "LWPOLYLINE": 2}, {0, 2},
            (0.221727, 0.221730, 0.295638, 0.295638, 0.295638, 0.369546,
             0.369546, 0.473250, 0.473250, 0.831482, 1.0),
            0.184774, 0.073911, 2.956378,
            "eleven-line-crossed-actuator-switch-ignore-v1",
        ),
    )
    histogram = shape.get("entity_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    arcs = shape.get("normalized_arcs") or []
    segments = shape.get("normalized_line_segments") or []
    if (
        len(contacts) != 2 or len(arcs) != 1
        or (shape.get("normalized_circles") or [])
        or (shape.get("text_values") or [])
        or (shape.get("normalized_open_lwpolylines") or [])
    ):
        return None
    try:
        lengths = sorted(math.dist(segment["start"][:2], segment["end"][:2]) for segment in segments)
        maximum = max(lengths)
        ratios = tuple(length / maximum for length in lengths)
        arc_ratio = float(arcs[0]["radius"]) / maximum
        contact_radii = [
            float(contact.get("chord_radius", contact.get("radius"))) / maximum
            for contact in contacts
        ]
        span_ratio = math.dist(contacts[0]["center"][:2], contacts[1]["center"][:2]) / maximum
        sweep = float(arcs[0]["sweep_deg"])
    except (IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if abs(sweep - 180.0) > 0.1 or abs(contact_radii[0] - contact_radii[1]) > 0.002:
        return None
    for expected_histogram, allowed_ports, expected_ratios, expected_arc, expected_contact, expected_span, rule in templates:
        if (
            histogram == expected_histogram
            and port_count in allowed_ports
            and len(ratios) == len(expected_ratios)
            and max(abs(actual - expected) for actual, expected in zip(ratios, expected_ratios)) <= 0.008
            and abs(arc_ratio - expected_arc) <= 0.005
            and max(abs(radius - expected_contact) for radius in contact_radii) <= 0.003
            and abs(span_ratio - expected_span) <= 0.012
        ):
            return rule
    return None


def _is_line_only_actuated_switch_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    histogram = shape.get("entity_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    if not (
        histogram == {"LINE": 8, "LWPOLYLINE": 2}
        and port_count in {0, 2}
        and len(contacts) == 2
        and len(segments) == 8
        and not (shape.get("arc_radii") or [])
        and not (shape.get("circle_radii") or [])
        and not (shape.get("text_values") or [])
    ):
        return False
    expected = (0.220588, 0.294117, 0.367647, 0.367647,
                0.588237, 0.588237, 0.791936, 1.0)
    try:
        lengths = sorted(math.dist(segment["start"][:2], segment["end"][:2]) for segment in segments)
        maximum = max(lengths)
        ratios = tuple(length / maximum for length in lengths)
        contact_radii = [
            float(contact.get("chord_radius", contact.get("radius"))) / maximum
            for contact in contacts
        ]
        span = math.dist(contacts[0]["center"][:2], contacts[1]["center"][:2]) / maximum
    except (IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return False
    return bool(
        max(abs(actual - target) for actual, target in zip(ratios, expected)) <= 0.008
        and max(abs(radius - 0.078431) for radius in contact_radii) <= 0.003
        and abs(contact_radii[0] - contact_radii[1]) <= 0.002
        and abs(span - 1.764708) <= 0.012
    )


def _is_wfs_polarity_two_port_geometry(shape: Mapping[str, Any], *, port_count: int) -> bool:
    """Strict normalized census shape for the WFS rounded polarity capsule."""
    h = shape.get("entity_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    values = {str(v).strip() for v in shape.get("text_values") or []}
    try:
        parsed_contacts = sorted(
            [
                (
                    (float(c["center"][0]), float(c["center"][1])),
                    float(c.get("chord_radius", c.get("radius"))),
                )
                for c in contacts
            ],
            key=lambda item: item[1],
        )
        radii = [radius for _, radius in parsed_contacts]
        cr = [float(c.get("radius")) for c in circles]
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    if not (
        port_count == 2 and h.get("CIRCLE") == 2 and h.get("LWPOLYLINE") == 3
        and h.get("TEXT") == 2 and values == {"+", "-"}
        and len(contacts) == 3 and len(cr) == 2 and max(cr) - min(cr) <= 1e-6 * max(max(cr), 1.0)
        and len(radii) == 3 and radii[0] > 0 and radii[1] / radii[2] < 0.2
    ):
        return False
    outer = [center for center, _ in parsed_contacts[:2]]
    body_center, body_radius = parsed_contacts[2]
    span = math.dist(*outer)
    midpoint = ((outer[0][0] + outer[1][0]) / 2, (outer[0][1] + outer[1][1]) / 2)
    if not (
        1.95 <= span / body_radius <= 2.05
        and math.dist(midpoint, body_center) <= body_radius * .015
        and .24 <= sum(cr) / 2 / body_radius <= .26
    ):
        return False
    axis = ((outer[1][0] - outer[0][0]) / span, (outer[1][1] - outer[0][1]) / span)
    circle_offsets = sorted(
        ((float(circle["center"][0]) - body_center[0]) * axis[0]
         + (float(circle["center"][1]) - body_center[1]) * axis[1]) / body_radius
        for circle in circles
    )
    return -0.64 <= circle_offsets[0] <= -0.61 and 0.61 <= circle_offsets[1] <= 0.64


def _propose_wfs_polarity_ports(block: Any, *, source_id: str) -> tuple[ProposedPort, ...]:
    contacts = []
    polarity_texts: list[tuple[str, tuple[float, float]]] = []
    for entity in block:
        kind = str(entity.dxftype()).upper()
        if kind == "TEXT":
            try:
                value = str(entity.dxf.text).strip()
                point = entity.dxf.insert
                if value in {"+", "-"}:
                    polarity_texts.append((value, (float(point.x), float(point.y))))
            except Exception:
                pass
            continue
        if kind != "LWPOLYLINE" or not bool(getattr(entity, "closed", False)):
            continue
        try:
            points = list(entity.get_points("xyb"))
            if not points or not any(abs(float(p[2])) > 1e-9 for p in points):
                continue
            xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
            contacts.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0,
                             max(max(xs) - min(xs), max(ys) - min(ys))))
        except Exception:
            continue
    if len(contacts) != 3:
        return ()
    small = sorted(contacts, key=lambda c: c[2])[:2]
    if (
        small[0][2] <= 0
        or small[1][2] / max(contacts, key=lambda c: c[2])[2] >= 0.2
        or {value for value, _ in polarity_texts} != {"+", "-"}
    ):
        return ()
    center = (sum(c[0] for c in small) / 2.0, sum(c[1] for c in small) / 2.0)
    axis = _normalize((small[1][0] - small[0][0], small[1][1] - small[0][1]))
    ordered = sorted(small, key=lambda c: c[0] * axis[0] + c[1] * axis[1])
    ordered_texts = sorted(
        polarity_texts, key=lambda item: item[1][0] * axis[0] + item[1][1] * axis[1]
    )
    return tuple(
        ProposedPort(
            port_id=f"MP{index}", local_position=(contact[0], contact[1], 0.0),
            outward_direction=_normalize((contact[0] - center[0], contact[1] - center[1])),
            port_type="ELECTRICAL", confidence=0.98,
            evidence_codes=("WFS_AXIAL_CONTACT", "POLARITY_TEXT_NOT_PORT"),
            source_ids=(source_id,), notes="Independent axial terminal; no internal union.",
            component_pin=polarity[0],
        )
        for index, (contact, polarity) in enumerate(zip(ordered, ordered_texts), 1)
    )


def _is_four_numbered_contact_panel_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a 2x2 numbered panel with four isolated outward contacts."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    ellipses = shape.get("normalized_ellipses") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count == 4
            and int(histogram.get("LINE", 0)) == 4
            and int(histogram.get("LWPOLYLINE", 0)) == 4
            and int(histogram.get("CIRCLE", 0)) + int(histogram.get("ELLIPSE", 0)) == 4
            and int(histogram.get("TEXT", 0)) == 4
            and int(histogram.get("ARC", 0)) == 0
            and len(contacts) == 4
            and len(circles) + len(ellipses) == 4
            and len(segments) == 4
        ):
            return False
        values = sorted(
            int(str(value).strip()) for value in shape.get("text_values") or []
        )
        parsed_contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        parsed_circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in circles
        ]
        parsed_circles.extend(
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("radius") or item.get("major_radius")),
            )
            for item in ellipses
        )
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    if values != list(range(values[0], values[0] + 4)):
        return False
    contact_radii = [radius for _, radius in parsed_contacts]
    circle_radii = [radius for _, radius in parsed_circles]
    if (
        min(contact_radii) <= 1e-9
        or max(contact_radii) / min(contact_radii) > 1.05
        or min(circle_radii) <= 1e-9
        or max(circle_radii) / min(circle_radii) > 1.05
    ):
        return False
    mean_contact_radius = sum(contact_radii) / 4.0
    mean_circle_radius = sum(circle_radii) / 4.0
    if not 4.65 <= mean_circle_radius / mean_contact_radius <= 5.05:
        return False
    if not (
        _is_rotation_invariant_contact_grid(contacts, columns=2, rows=2)
        and _is_rotation_invariant_contact_grid(circles, columns=2, rows=2)
    ):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    grid_center = (
        sum(center[0] for center, _ in parsed_circles) / 4.0,
        sum(center[1] for center, _ in parsed_circles) / 4.0,
    )
    used_circles: set[int] = set()
    for contact_center, _ in parsed_contacts:
        nearest = min(
            (
                (distance(contact_center, circle_center), index, circle_center)
                for index, (circle_center, _) in enumerate(parsed_circles)
            ),
            key=lambda item: item[0],
        )
        if nearest[1] in used_circles:
            return False
        if not 0.955 <= nearest[0] / mean_circle_radius <= 1.045:
            return False
        circle_center = nearest[2]
        outward = (
            circle_center[0] - grid_center[0],
            circle_center[1] - grid_center[1],
        )
        contact_vector = (
            contact_center[0] - circle_center[0],
            contact_center[1] - circle_center[1],
        )
        if outward[0] * contact_vector[0] + outward[1] * contact_vector[1] <= 0.0:
            return False
        used_circles.add(nearest[1])
    if len(used_circles) != 4:
        return False

    line_rows = []
    for start, end in parsed_segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        line_rows.append(
            {
                "start": start,
                "end": end,
                "unit": (dx / length, dy / length),
                "length": length,
                "midpoint": ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
            }
        )
    if len(line_rows) == 3:
        for stem_index, stem in enumerate(line_rows):
            parallel = [
                row for index, row in enumerate(line_rows) if index != stem_index
            ]
            parallel_dot = abs(
                parallel[0]["unit"][0] * parallel[1]["unit"][0]
                + parallel[0]["unit"][1] * parallel[1]["unit"][1]
            )
            if parallel_dot < 0.98 or any(
                abs(
                    stem["unit"][0] * row["unit"][0]
                    + stem["unit"][1] * row["unit"][1]
                )
                > 0.05
                for row in parallel
            ):
                continue
            lengths = sorted(row["length"] for row in parallel)
            if not (
                0.48 <= lengths[0] / lengths[1] <= 0.52
                and 0.85 <= stem["length"] / lengths[1] <= 0.90
            ):
                continue
            projections = sorted(
                (row["midpoint"][0] - stem["start"][0]) * stem["unit"][0]
                + (row["midpoint"][1] - stem["start"][1]) * stem["unit"][1]
                for row in parallel
            )
            if not (
                abs(projections[0]) <= mean_contact_radius * 0.08
                and abs(projections[1] - stem["length"])
                <= mean_contact_radius * 0.08
            ):
                continue
            if all(
                abs(
                    (row["midpoint"][0] - stem["start"][0])
                    * parallel[0]["unit"][0]
                    + (row["midpoint"][1] - stem["start"][1])
                    * parallel[0]["unit"][1]
                )
                <= mean_contact_radius * 0.08
                for row in parallel
            ):
                return True
        return False
    for stem_index, stem in enumerate(line_rows):
        parallel = [row for index, row in enumerate(line_rows) if index != stem_index]
        if not all(
            abs(row["unit"][0] * parallel[0]["unit"][0]
                + row["unit"][1] * parallel[0]["unit"][1]) >= 0.98
            for row in parallel[1:]
        ):
            continue
        if any(
            abs(stem["unit"][0] * row["unit"][0]
                + stem["unit"][1] * row["unit"][1]) > 0.05
            for row in parallel
        ):
            continue
        lengths = sorted(row["length"] for row in parallel)
        if not (
            0.48 <= lengths[0] / lengths[2] <= 0.52
            and 0.98 <= lengths[1] / lengths[2] <= 1.02
            and 1.88 <= stem["length"] / lengths[2] <= 1.92
        ):
            continue
        projections = sorted(
            (row["midpoint"][0] - stem["start"][0]) * stem["unit"][0]
            + (row["midpoint"][1] - stem["start"][1]) * stem["unit"][1]
            for row in parallel
        )
        if not (
            abs(projections[0]) <= mean_contact_radius * 0.08
            and abs(projections[2] - stem["length"]) <= mean_contact_radius * 0.08
            and 0.48 <= projections[1] / stem["length"] <= 0.51
        ):
            continue
        if all(
            abs(
                (row["midpoint"][0] - stem["start"][0]) * parallel[0]["unit"][0]
                + (row["midpoint"][1] - stem["start"][1]) * parallel[0]["unit"][1]
            ) <= mean_contact_radius * 0.08
            for row in parallel
        ):
            return True
    return False


def _is_two_column_regular_grid(
    items: Sequence[Any], *, rows: int, tolerance: float = 0.08
) -> bool:
    """Recognize a rotation/reflection-invariant two-column regular grid."""

    try:
        points = [
            (
                float((item.get("center", item))[0]),
                float((item.get("center", item))[1]),
            )
            for item in items
            if isinstance(item, Mapping)
        ]
    except (IndexError, TypeError, ValueError):
        return False
    if rows < 2 or len(points) != rows * 2:
        return False
    center = (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
    covariance_xx = sum((point[0] - center[0]) ** 2 for point in points)
    covariance_yy = sum((point[1] - center[1]) ** 2 for point in points)
    covariance_xy = sum(
        (point[0] - center[0]) * (point[1] - center[1]) for point in points
    )
    angle = 0.5 * math.atan2(
        2.0 * covariance_xy, covariance_xx - covariance_yy
    )
    axes = (
        (math.cos(angle), math.sin(angle)),
        (-math.sin(angle), math.cos(angle)),
    )

    def matches(column_axis: tuple[float, float], row_axis: tuple[float, float]) -> bool:
        column_values = sorted(
            point[0] * column_axis[0] + point[1] * column_axis[1]
            for point in points
        )
        left, right = column_values[:rows], column_values[rows:]
        column_gap = sum(right) / rows - sum(left) / rows
        if column_gap <= 1e-9:
            return False
        if max(max(left) - min(left), max(right) - min(right)) > column_gap * tolerance:
            return False

        row_values = sorted(
            point[0] * row_axis[0] + point[1] * row_axis[1]
            for point in points
        )
        row_groups = [row_values[index : index + 2] for index in range(0, len(row_values), 2)]
        row_centers = [sum(group) / 2.0 for group in row_groups]
        gaps = [
            row_centers[index + 1] - row_centers[index]
            for index in range(len(row_centers) - 1)
        ]
        if not gaps or min(gaps) <= 1e-9:
            return False
        mean_gap = sum(gaps) / len(gaps)
        return bool(
            max(abs(group[1] - group[0]) for group in row_groups)
            <= mean_gap * tolerance
            and max(abs(gap - mean_gap) for gap in gaps) <= mean_gap * tolerance
        )

    return matches(axes[0], axes[1]) or matches(axes[1], axes[0])


def _is_numbered_round_contact_array_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the reusable 2xN numbered isolated-contact component family."""

    if port_count < 8 or port_count > 32 or port_count % 2:
        return False
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    try:
        if not (
            int(histogram.get("TEXT", 0)) == port_count
            and int(histogram.get("CIRCLE", 0)) == port_count
            and int(histogram.get("LWPOLYLINE", 0)) == port_count + 1
            and sum(int(value) for value in histogram.values()) == port_count * 3 + 1
            and len(contacts) == port_count + 1
            and len(circles) == port_count
        ):
            return False
        values = sorted(int(str(value).strip()) for value in shape.get("text_values") or [])
        parsed_contacts = sorted(
            [
                (
                float(item.get("chord_radius") or item["radius"]),
                item,
                )
                for item in contacts
            ],
            key=lambda row: row[0],
        )
        parsed_circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in circles
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    if values != list(range(1, port_count + 1)):
        return False
    small_contacts = [item for _, item in parsed_contacts[:port_count]]
    small_radii = [radius for radius, _ in parsed_contacts[:port_count]]
    body_radius = parsed_contacts[-1][0]
    circle_radii = [radius for _, radius in parsed_circles]
    if (
        min(small_radii) <= 1e-9
        or max(small_radii) / min(small_radii) > 1.05
        or body_radius / max(small_radii) < 20.0
        or min(circle_radii) <= 1e-9
        or max(circle_radii) / min(circle_radii) > 1.05
        or not _is_two_column_regular_grid(small_contacts, rows=port_count // 2)
        or not _is_two_column_regular_grid(circles, rows=port_count // 2)
    ):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    circle_center = (
        sum(center[0] for center, _ in parsed_circles) / port_count,
        sum(center[1] for center, _ in parsed_circles) / port_count,
    )
    used_contacts: set[int] = set()
    for center, radius in parsed_circles:
        nearest = min(
            (
                (
                    distance(center, (float(contact["center"][0]), float(contact["center"][1]))),
                    index,
                    (float(contact["center"][0]), float(contact["center"][1])),
                )
                for index, contact in enumerate(small_contacts)
            ),
            key=lambda item: item[0],
        )
        if nearest[1] in used_contacts or not 1.55 <= nearest[0] / radius <= 2.30:
            return False
        outward = (center[0] - circle_center[0], center[1] - circle_center[1])
        contact_offset = (nearest[2][0] - center[0], nearest[2][1] - center[1])
        if outward[0] * contact_offset[0] + outward[1] * contact_offset[1] <= 0.0:
            return False
        used_contacts.add(nearest[1])
    return len(used_contacts) == port_count


def _is_two_column_lopsided_regular_grid(
    rows: Sequence[Mapping[str, Any]], *, tolerance: float = 0.08
) -> bool:
    """Recognize two regular columns where one column has one extra end row."""

    try:
        points = [
            (float(row["center"][0]), float(row["center"][1])) for row in rows
        ]
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    if len(points) != 11:
        return False
    center = (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
    covariance_xx = sum((point[0] - center[0]) ** 2 for point in points)
    covariance_yy = sum((point[1] - center[1]) ** 2 for point in points)
    covariance_xy = sum(
        (point[0] - center[0]) * (point[1] - center[1]) for point in points
    )
    angle = 0.5 * math.atan2(2.0 * covariance_xy, covariance_xx - covariance_yy)
    axes = [
        (math.cos(angle), math.sin(angle)),
        (-math.sin(angle), math.cos(angle)),
    ]
    for left_index, left in enumerate(points):
        for right in points[left_index + 1 :]:
            dx, dy = right[0] - left[0], right[1] - left[1]
            norm = math.hypot(dx, dy)
            if norm > 1e-9:
                axes.append((dx / norm, dy / norm))

    def matches(column_axis: tuple[float, float], row_axis: tuple[float, float]) -> bool:
        projected = sorted(
            (
                point[0] * column_axis[0] + point[1] * column_axis[1],
                point[0] * row_axis[0] + point[1] * row_axis[1],
            )
            for point in points
        )
        gaps = [
            projected[index + 1][0] - projected[index][0]
            for index in range(len(projected) - 1)
        ]
        split = max(range(len(gaps)), key=gaps.__getitem__) + 1
        columns = (projected[:split], projected[split:])
        if sorted(len(column) for column in columns) != [5, 6]:
            return False
        column_gap = abs(
            sum(value[0] for value in columns[1]) / len(columns[1])
            - sum(value[0] for value in columns[0]) / len(columns[0])
        )
        if column_gap <= 1e-9:
            return False
        if any(
            max(value[0] for value in column) - min(value[0] for value in column)
            > column_gap * tolerance
            for column in columns
        ):
            return False
        row_sets = [sorted(value[1] for value in column) for column in columns]
        row_gaps = [
            values[index + 1] - values[index]
            for values in row_sets
            for index in range(len(values) - 1)
        ]
        if not row_gaps or min(row_gaps) <= 1e-9:
            return False
        mean_gap = sum(row_gaps) / len(row_gaps)
        if max(abs(gap - mean_gap) for gap in row_gaps) > mean_gap * tolerance:
            return False
        shorter, longer = sorted(row_sets, key=len)
        return any(
            max(abs(left - right) for left, right in zip(shorter, window))
            <= mean_gap * tolerance
            for window in (longer[:-1], longer[1:])
        )

    return any(
        matches(axis, (-axis[1], axis[0]))
        or matches((-axis[1], axis[0]), axis)
        for axis in axes
    )


def _is_functional_round_contact_array_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the 1..8/C+/G-/R- isolated outward-contact component."""

    if port_count != 11:
        return False
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    try:
        if not (
            int(histogram.get("TEXT", 0)) == 11
            and int(histogram.get("CIRCLE", 0)) == 11
            and int(histogram.get("LWPOLYLINE", 0)) == 12
            and sum(int(value) for value in histogram.values()) == 34
            and len(contacts) == 12
            and len(circles) == 11
        ):
            return False
        if {str(value).strip().upper() for value in shape.get("text_values") or []} != {
            "1", "2", "3", "4", "5", "6", "7", "8", "C+", "G-", "R-"
        }:
            return False
        parsed_contacts = sorted(
            [
                (
                    float(item.get("chord_radius") or item["radius"]),
                    item,
                )
                for item in contacts
            ],
            key=lambda row: row[0],
        )
        parsed_circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in circles
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    small_contacts = [item for _, item in parsed_contacts[:11]]
    small_radii = [radius for radius, _ in parsed_contacts[:11]]
    circle_radii = [radius for _, radius in parsed_circles]
    if (
        min(small_radii) <= 1e-9
        or max(small_radii) / min(small_radii) > 1.05
        or parsed_contacts[-1][0] / max(small_radii) < 20.0
        or min(circle_radii) <= 1e-9
        or max(circle_radii) / min(circle_radii) > 1.05
        or not _is_two_column_lopsided_regular_grid(circles)
        or not _is_two_column_lopsided_regular_grid(small_contacts)
    ):
        return False
    circle_center = (
        sum(center[0] for center, _ in parsed_circles) / 11.0,
        sum(center[1] for center, _ in parsed_circles) / 11.0,
    )
    used_contacts: set[int] = set()
    for center, radius in parsed_circles:
        nearest = min(
            (
                (
                    _distance(
                        center,
                        (float(contact["center"][0]), float(contact["center"][1])),
                    ),
                    index,
                    (float(contact["center"][0]), float(contact["center"][1])),
                )
                for index, contact in enumerate(small_contacts)
            ),
            key=lambda item: item[0],
        )
        if nearest[1] in used_contacts or not 1.55 <= nearest[0] / radius <= 2.30:
            return False
        outward = (center[0] - circle_center[0], center[1] - circle_center[1])
        contact_offset = (nearest[2][0] - center[0], nearest[2][1] - center[1])
        if outward[0] * contact_offset[0] + outward[1] * contact_offset[1] <= 0.0:
            return False
        used_contacts.add(nearest[1])
    return len(used_contacts) == 11


def _is_eight_numbered_side_contact_panel_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the complete 2x4 numbered equipment-side contact panel."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    rectangles = shape.get("normalized_closed_straight_lwpolylines") or []
    nested = shape.get("normalized_inserts") or []
    try:
        if not (
            port_count == 8
            and int(histogram.get("LINE", 0)) == 13
            and int(histogram.get("LWPOLYLINE", 0)) == 17
            and int(histogram.get("TEXT", 0)) == 31
            and int(histogram.get("INSERT", 0)) == 1
            and int(histogram.get("CIRCLE", 0)) == 0
            and int(histogram.get("ARC", 0)) == 0
            and len(contacts) == 8
            and len(rectangles) == 9
            and len(nested) == 1
        ):
            return False
        numeric_values = sorted(
            int(str(value).strip())
            for value in shape.get("text_values") or []
            if re.fullmatch(r"[1-8]", str(value).strip())
        )
        parsed_contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        square_rows = []
        for item in rectangles:
            edges = [float(value) for value in item.get("edge_lengths") or []]
            if len(edges) != 4 or min(edges) <= 1e-9:
                continue
            if max(edges) / min(edges) <= 1.05:
                square_rows.append(
                    {
                        "center": [
                            float(item["center"][0]),
                            float(item["center"][1]),
                        ],
                        "side": sum(edges) / 4.0,
                    }
                )
        child_histogram = nested[0].get("child_entity_histogram") or {}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    if numeric_values != list(range(1, 9)) or len(square_rows) != 8:
        return False
    if not (
        int(child_histogram.get("LINE", 0)) == 12
        and int(child_histogram.get("LWPOLYLINE", 0)) == 1
        and len(child_histogram) == 2
    ):
        return False
    radii = [radius for _, radius in parsed_contacts]
    square_sides = [float(item["side"]) for item in square_rows]
    if (
        min(radii) <= 1e-9
        or max(radii) / min(radii) > 1.05
        or min(square_sides) <= 1e-9
        or max(square_sides) / min(square_sides) > 1.05
    ):
        return False
    if not (
        _is_rotation_invariant_contact_grid(
            contacts, columns=2, rows=4, tolerance=0.08
        )
        and _is_rotation_invariant_contact_grid(
            square_rows, columns=2, rows=4, tolerance=0.08
        )
    ):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    panel_center = (
        sum(center[0] for center, _ in parsed_contacts) / 8.0,
        sum(center[1] for center, _ in parsed_contacts) / 8.0,
    )
    used_squares: set[int] = set()
    for contact_center, _ in parsed_contacts:
        nearest = min(
            (
                (
                    distance(contact_center, tuple(square["center"])),
                    index,
                    tuple(square["center"]),
                    float(square["side"]),
                )
                for index, square in enumerate(square_rows)
            ),
            key=lambda item: item[0],
        )
        if nearest[1] in used_squares or not 0.48 <= nearest[0] / nearest[3] <= 0.52:
            return False
        outward = (
            nearest[2][0] - panel_center[0],
            nearest[2][1] - panel_center[1],
        )
        contact_offset = (
            contact_center[0] - nearest[2][0],
            contact_center[1] - nearest[2][1],
        )
        if outward[0] * contact_offset[0] + outward[1] * contact_offset[1] <= 0.0:
            return False
        used_squares.add(nearest[1])
    return len(used_squares) == 8


def _is_four_contact_isolated_frame_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a 2x2 four-port mechanism while inferring no switch state."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    try:
        if not (
            port_count == 4
            and int(histogram.get("LINE", 0)) == 15
            and int(histogram.get("LWPOLYLINE", 0)) == 8
            and int(histogram.get("CIRCLE", 0)) == 4
            and int(histogram.get("TEXT", 0)) == 0
            and len(contacts) == 8
            and len(circles) == 4
            and len(shape.get("normalized_line_segments") or []) == 15
        ):
            return False
        parsed_contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        parsed_circles = [
            ((float(item["center"][0]), float(item["center"][1])), float(item["radius"]))
            for item in circles
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    def distance(left, right) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    contact_radii = [radius for _, radius in parsed_contacts]
    circle_radii = [radius for _, radius in parsed_circles]
    if min(contact_radii) <= 1e-9 or max(contact_radii) / min(contact_radii) > 1.05:
        return False
    if min(circle_radii) <= 1e-9 or max(circle_radii) / min(circle_radii) > 1.05:
        return False
    if not (2.9 <= (sum(circle_radii) / 4.0) / (sum(contact_radii) / 8.0) <= 3.1):
        return False
    inner = [
        center
        for center, _ in parsed_contacts
        if any(distance(center, circle_center) <= max(circle_radii) * 0.03 for circle_center, _ in parsed_circles)
    ]
    outer = [
        center
        for center, _ in parsed_contacts
        if center not in inner
    ]
    if len(inner) != 4 or len(outer) != 4:
        return False
    inner_rows = [{"center": list(center)} for center in inner]
    outer_rows = [{"center": list(center)} for center in outer]
    if not (
        _is_rotation_invariant_contact_grid(inner_rows, columns=2, rows=2)
        and _is_rotation_invariant_contact_grid(outer_rows, columns=2, rows=2)
    ):
        return False
    inner_center = (
        sum(point[0] for point in inner) / 4.0,
        sum(point[1] for point in inner) / 4.0,
    )
    outer_center = (
        sum(point[0] for point in outer) / 4.0,
        sum(point[1] for point in outer) / 4.0,
    )
    return distance(inner_center, outer_center) <= max(circle_radii) * 0.05


def _is_backplate_table_container_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a dense multi-plugin backplate table without block identity."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping):
        return False
    try:
        text_count = int(histogram.get("TEXT", 0)) + int(histogram.get("MTEXT", 0))
        line_count = int(histogram.get("LINE", 0))
        polyline_count = int(histogram.get("LWPOLYLINE", 0)) + int(histogram.get("POLYLINE", 0))
        hatch_count = int(histogram.get("HATCH", 0))
        aspect = float(shape.get("oriented_aspect_ratio") or 0.0)
    except (TypeError, ValueError):
        return False
    values = [str(value or "").strip().upper() for value in shape.get("text_values") or []]
    row_numbers = {
        int(value)
        for value in values
        if re.fullmatch(r"(?:0?[1-9]|[12][0-9]|3[0-2])", value)
    }
    header_prefixes = {
        match.group(1)
        for value in values
        if (match := re.match(r"^([A-Z]{2,6}\d{3,4}[A-Z])(?:\b|\(|$)", value))
    }
    slot_numbers = {value for value in values if value in {str(number) for number in range(1, 9)}}
    return bool(
        port_count == 2
        and text_count >= 150
        and line_count >= 50
        and polyline_count >= 150
        and hatch_count <= 12
        and 1.4 <= aspect <= 2.5
        and len(row_numbers) >= 28
        and len(header_prefixes) >= 3
        and len(slot_numbers) >= 5
    )


def classify_definition_family(
    proposal: Mapping[str, Any],
    *,
    fingerprint: str | None = None,
) -> dict[str, Any]:
    """Classify a definition into a versioned family without granting authority."""

    observed_fingerprint = str(
        fingerprint or proposal.get("definition_fingerprint") or ""
    ).strip()
    reviewed_policy = human_symbol_port_policy(observed_fingerprint)
    summary = proposal.get("geometry_summary")
    shape = summary.get("shape_features") if isinstance(summary, Mapping) else None
    shape = shape if isinstance(shape, Mapping) else {}
    ports = [item for item in proposal.get("ports") or [] if isinstance(item, Mapping)]
    try:
        width = float(shape.get("width", 0.0))
        height = float(shape.get("height", 0.0))
        primitive_count = int(shape.get("primitive_count", 0))
        arc_count = len(shape.get("arc_radii") or [])
        circle_count = len(shape.get("circle_radii") or [])
    except (TypeError, ValueError):
        width = height = 0.0
        primitive_count = arc_count = circle_count = 0
    short_side = min(width, height)
    aspect_ratio = (
        max(width, height) / short_side if short_side > 1e-9 else 0.0
    )

    table_container_match = _is_backplate_table_container_geometry(
        shape, port_count=len(ports)
    )
    panel_match = _is_communication_multiport_panel_geometry(
        shape, port_count=len(ports)
    )
    ignore_match = (
        None
        if table_container_match or panel_match
        else _match_confirmed_ignore_geometry_family(
            shape, port_count=len(ports), aspect_ratio=aspect_ratio
        )
    )
    machine_family: str | None = (
        "structural.backplate_table_container.v1"
        if table_container_match
        else "component.external_communication_panel.v1"
        if panel_match
        else ignore_match[0]
        if ignore_match
        else None
    )
    matched_rule_id: str | None = (
        "dense-multi-plugin-backplate-table-v1"
        if table_container_match
        else "repeated-labelled-communication-pin-cells-v1"
        if panel_match
        else ignore_match[1]
        if ignore_match
        else None
    )
    classifier_status = "MATCHED" if table_container_match or panel_match or ignore_match else "UNKNOWN"
    confidence = 0.99 if table_container_match else 0.98 if panel_match else ignore_match[2] if ignore_match else 0.0
    if machine_family is None and _is_wfs_polarity_two_port_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_wfs_polarity_two_port.v1"
        matched_rule_id = "wfs-rounded-polarity-axial-two-port-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_numbered_round_contact_array_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "numbered-round-contact-array-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_functional_round_contact_array_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "numbered-functional-contact-array-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_four_numbered_contact_panel_geometry(
        shape, port_count=len(ports)
    ):
        elxal_family = (
            reviewed_policy.get("family_id") if reviewed_policy else None
        )
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "four-numbered-independent-contact-panel-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _is_eight_numbered_side_contact_panel_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "eight-numbered-side-contact-panel-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_four_contact_isolated_frame_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "four-contact-isolated-switch-frame-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _is_four_radial_isolated_terminal_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "four-radial-isolated-terminal-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_round_body_isolated_two_port_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "round-body-isolated-axial-two-port-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_dual_frame_isolated_two_port_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "dual-frame-isolated-axial-two-port-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_triangle_body_isolated_two_port_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "triangle-body-isolated-axial-two-port-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_three_contact_socket_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "three-contact-labelled-socket-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _is_four_contact_terminal_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "labelled_terminal.generic.v1"
        matched_rule_id = "four-orthogonal-contact-terminal-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _is_slash_circle_two_contact_terminal_geometry(
        shape, port_count=len(ports)
    ):
        machine_family = "labelled_terminal.generic.v1"
        matched_rule_id = "slash-circle-two-contact-terminal-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and is_high_confidence_terminal_geometry(proposal):
        machine_family = "labelled_terminal.generic.v1"
        matched_rule_id = "compact-equal-arc-terminal-v1"
        classifier_status = "MATCHED"
        confidence = 0.9
    elif machine_family is None and _has_fjl_line_bound_two_port_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "fjl-two-circle-four-contact-line-bound-ports-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _kk_of_main_port_count(shape) == len(ports):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = f"kk-of-selective-{len(ports)}-main-port-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _is_kk3p_six_port_geometry(
        shape, port_count=len(ports), width=width, height=height
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "numbered-3x2-six-contact-grid-v1"
        classifier_status = "MATCHED"
        confidence = 0.97
    elif machine_family is None and _is_high_confidence_external_multi_port_geometry(
        shape, port_count=len(ports), width=width, height=height
    ):
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "repeated-round-body-external-ports-v1"
        classifier_status = "MATCHED"
        confidence = 0.9
    elif machine_family is None and _has_single_row_contact_mechanism_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_row_contact.v1"
        matched_rule_id = "single-row-circle-contact-mechanism-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _has_two_contact_mechanical_actuator_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "two-contact-mechanical-actuator-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _has_named_four_contact_two_port_strip_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "four-contact-two-circle-named-strip-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and _has_vertical_two_port_box_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "vertical-numbered-two-port-box-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _has_horizontal_numbered_two_circle_box_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "horizontal-numbered-two-circle-box-v1"
        classifier_status = "MATCHED"
        confidence = 0.99
    elif machine_family is None and _has_named_two_row_box_topology(
        shape, port_count=len(ports)
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "named-two-row-box-four-contact-v1"
        classifier_status = "MATCHED"
        confidence = 0.98
    elif machine_family is None and len(ports) >= 4 and primitive_count >= 16 and max(width, height) > 0.0:
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "repeated-external-port-geometry-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.75
    elif machine_family is None and (
        len(ports) == 2
        and aspect_ratio >= 4.0
        and arc_count + circle_count >= 2
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "elongated-round-end-two-port-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.7
    elif machine_family is None and len(ports) == 2 and aspect_ratio >= 4.0 and arc_count == 0:
        machine_family = "switch.open.candidate.v1"
        matched_rule_id = "elongated-gap-two-port-candidate-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.4
    elif machine_family is None and len(ports) == 2 and arc_count >= 4:
        machine_family = "line_break.non_connective.candidate.v1"
        matched_rule_id = "multi-arc-line-break-candidate-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.45

    reviewed_family = reviewed_policy.get("family_id") if reviewed_policy else None
    # For the newly adjudicated WFS/ELXAL families, the digest is provenance
    # only.  A reviewed member must still pass the complete subtype geometry
    # rule; an altered block with the same digest must fail closed.
    geometry_bound_review = {
        "component.external_wfs_polarity_two_port.v1",
    }
    if reviewed_family in geometry_bound_review and machine_family != reviewed_family:
        reviewed_family = None
    family_id = machine_family or reviewed_family
    source = "MACHINE_GEOMETRY_RULE" if machine_family else "UNKNOWN"
    if reviewed_family:
        source = (
            "MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER"
            if machine_family == reviewed_family
            else "HUMAN_EXACT_MEMBER"
        )
        family_id = reviewed_family
        classifier_status = "HUMAN_CONFIRMED_MEMBER"
        confidence = 1.0
        matched_rule_id = matched_rule_id or "human-exact-member-v1"

    return {
        "family_schema_version": FAMILY_CLASSIFICATION_VERSION,
        "family_id": family_id,
        "family_version": "1" if family_id else None,
        "classifier_status": classifier_status,
        "classifier_confidence": confidence,
        "matched_family_rule_id": matched_rule_id,
        "family_evidence_source": source,
        "fingerprint_version": "local-geometry-fingerprint-v1",
        "exact_human_member": bool(reviewed_policy),
        "authority": "SHADOW_ONLY",
    }


def _has_grounded_three_row_cb_panel_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize a complete grounded three-row CB assembly by geometry.

    The parent skeleton, three repeated mechanism children, and one ground
    child are all required.  Names and fingerprints are intentionally absent.
    Distances are normalized by the three equal parent-contact radii, making
    the test invariant to parent rotation and uniform scale.
    """

    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    inserts = shape.get("normalized_inserts") or []
    try:
        if len(contacts) != 3 or len(segments) != 8 or len(inserts) != 4:
            return False
        parsed_contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
        parsed_inserts = [
            {
                "center": (
                    float(item["center"][0]),
                    float(item["center"][1]),
                ),
                "rotation": float(item.get("rotation_deg", 0.0)) % 360.0,
                "xscale": float(item.get("xscale", 1.0)),
                "yscale": float(item.get("yscale", 1.0)),
                "histogram": {
                    str(key): int(value)
                    for key, value in (item.get("child_entity_histogram") or {}).items()
                },
            }
            for item in inserts
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    radii = [radius for _, radius in parsed_contacts]
    radius = sum(radii) / 3.0
    if radius <= 1e-9 or max(radii) / min(radii) > 1.03:
        return False
    first, last = max(
        (
            (left, right)
            for index, left in enumerate(parsed_contacts)
            for right in parsed_contacts[index + 1 :]
        ),
        key=lambda pair: math.hypot(
            pair[1][0][0] - pair[0][0][0], pair[1][0][1] - pair[0][0][1]
        ),
    )
    column_vector = (last[0][0] - first[0][0], last[0][1] - first[0][1])
    column_span = math.hypot(column_vector[0], column_vector[1])
    if not 79.5 <= column_span / radius <= 80.5:
        return False
    column = (column_vector[0] / column_span, column_vector[1] / column_span)
    row_axis = (-column[1], column[0])
    center = ((first[0][0] + last[0][0]) / 2.0, (first[0][1] + last[0][1]) / 2.0)

    def project(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - center[0], point[1] - center[1]
        return (
            (dx * row_axis[0] + dy * row_axis[1]) / radius,
            (dx * column[0] + dy * column[1]) / radius,
        )

    contact_positions = sorted(
        (project(point) for point, _ in parsed_contacts), key=lambda item: item[1]
    )
    if any(abs(row) > 0.08 for row, _ in contact_positions):
        return False
    contact_levels = sorted(level for _, level in contact_positions)
    if any(
        abs(value - expected) > 0.15
        for value, expected in zip(contact_levels, (-40.0, 0.0, 40.0))
    ):
        return False

    projected_segments = []
    for start, end in parsed_segments:
        local_start, local_end = project(start), project(end)
        dx = local_end[0] - local_start[0]
        dy = local_end[1] - local_start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        projected_segments.append(
            {
                "start": local_start,
                "end": local_end,
                "length": length,
                "row_alignment": abs(dx) / length,
                "column_alignment": abs(dy) / length,
            }
        )
    spine_rows = [row for row in projected_segments if row["column_alignment"] >= 0.995]
    row_segments = [row for row in projected_segments if row["row_alignment"] >= 0.995]
    if len(spine_rows) != 1 or len(row_segments) != 7:
        return False
    spine = spine_rows[0]
    if (
        abs(spine["start"][0]) > 0.08
        or abs(spine["end"][0]) > 0.08
        or not 129.5 <= spine["length"] <= 130.5
    ):
        return False
    spine_levels = sorted((spine["start"][1], spine["end"][1]))
    overhangs = sorted(
        (
            contact_levels[0] - spine_levels[0],
            spine_levels[1] - contact_levels[-1],
        )
    )
    if not (9.5 <= overhangs[0] <= 10.5 and 39.5 <= overhangs[1] <= 40.5):
        return False

    groups: list[list[dict[str, Any]]] = []
    group_levels: list[float] = []
    for row in sorted(
        row_segments,
        key=lambda item: (item["start"][1] + item["end"][1]) / 2.0,
    ):
        level = (row["start"][1] + row["end"][1]) / 2.0
        if not group_levels or abs(level - group_levels[-1]) > 0.2:
            group_levels.append(level)
            groups.append([row])
        else:
            groups[-1].append(row)
    if len(groups) != 4 or sorted(len(group) for group in groups) != [1, 2, 2, 2]:
        return False
    ordered_levels = sorted(group_levels)
    if any(abs((ordered_levels[index + 1] - ordered_levels[index]) - 40.0) > 0.2 for index in range(3)):
        return False
    if not (
        all(any(abs(level - contact) <= 0.2 for level in ordered_levels) for contact in contact_levels)
        and min(
            abs(ordered_levels[0] - contact_levels[0]),
            abs(ordered_levels[-1] - contact_levels[-1]),
        ) <= 0.2
    ):
        return False

    single_index = next(index for index, group in enumerate(groups) if len(group) == 1)
    single_level = group_levels[single_index]
    if min(abs(single_level - contact) for contact in contact_levels) > 0.2:
        return False
    single = groups[single_index][0]
    if not 89.5 <= single["length"] <= 90.5:
        return False
    single_interval = sorted((single["start"][0], single["end"][0]))
    if min(abs(value) for value in single_interval) > 0.08:
        return False
    outward_sign = 1.0 if max(single_interval) > abs(min(single_interval)) else -1.0

    pair_levels = []
    for level, group in zip(group_levels, groups):
        if len(group) != 2:
            continue
        pair_levels.append(level)
        intervals = sorted(
            (
                sorted(
                    (
                        outward_sign * row["start"][0],
                        outward_sign * row["end"][0],
                    )
                )
                for row in group
            ),
            key=lambda interval: interval[0],
        )
        expected = ((0.0, 40.0), (70.0, 90.0))
        if any(
            abs(actual - target) > 0.25
            for interval, expected_interval in zip(intervals, expected)
            for actual, target in zip(interval, expected_interval)
        ):
            return False

    mechanism_histogram = {"ARC": 2, "LINE": 3, "LWPOLYLINE": 2}
    ground_histogram = {"LINE": 4, "LWPOLYLINE": 1}
    mechanisms = [item for item in parsed_inserts if item["histogram"] == mechanism_histogram]
    grounds = [item for item in parsed_inserts if item["histogram"] == ground_histogram]
    if len(mechanisms) != 3 or len(grounds) != 1:
        return False
    scales = []
    for item in parsed_inserts:
        if min(abs(item["xscale"]), abs(item["yscale"])) <= 1e-9:
            return False
        if max(abs(item["xscale"]), abs(item["yscale"])) / min(abs(item["xscale"]), abs(item["yscale"])) > 1.03:
            return False
        scales.append((abs(item["xscale"]) + abs(item["yscale"])) / 2.0)
    if max(scales) / min(scales) > 1.03:
        return False

    mechanism_rotation = mechanisms[0]["rotation"]
    if any(
        abs(((item["rotation"] - mechanism_rotation + 180.0) % 360.0) - 180.0) > 1.0
        for item in mechanisms[1:]
    ):
        return False
    ground_rotation_delta = (grounds[0]["rotation"] - mechanism_rotation) % 360.0
    if abs(ground_rotation_delta - 180.0) > 1.0:
        return False

    mechanism_positions = sorted(project(item["center"]) for item in mechanisms)
    if any(abs(outward_sign * row - 70.0) > 0.25 for row, _ in mechanism_positions):
        return False
    mechanism_levels = sorted(level for _, level in mechanism_positions)
    if any(abs(actual - expected) > 0.25 for actual, expected in zip(mechanism_levels, sorted(pair_levels))):
        return False
    ground_row, ground_level = project(grounds[0]["center"])
    return bool(
        abs(ground_row) <= 0.1
        and 9.5 <= abs(ground_level - single_level) <= 10.5
        and (
            ground_level < min(contact_levels) - 9.0
            or ground_level > max(contact_levels) + 9.0
        )
    )


def _has_closed_cable_sleeve_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize a two-semicircle closed cable sleeve by full topology."""

    arcs = shape.get("normalized_arcs") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if len(arcs) != 2 or len(segments) != 2:
            return False
        parsed_arcs = [
            {
                "center": (
                    float(item["center"][0]),
                    float(item["center"][1]),
                ),
                "radius": float(item["radius"]),
                "sweep": float(item.get("sweep_deg", 0.0)),
                "midpoint": (
                    float(item["midpoint"][0]),
                    float(item["midpoint"][1]),
                ),
            }
            for item in arcs
        ]
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    radii = [item["radius"] for item in parsed_arcs]
    radius = sum(radii) / 2.0
    if (
        radius <= 1e-9
        or max(radii) / min(radii) > 1.03
        or any(abs(item["sweep"] - 180.0) > 1.0 for item in parsed_arcs)
    ):
        return False
    first_center, second_center = (
        parsed_arcs[0]["center"], parsed_arcs[1]["center"]
    )
    axis_vector = (
        second_center[0] - first_center[0],
        second_center[1] - first_center[1],
    )
    spacing = math.hypot(axis_vector[0], axis_vector[1])
    if not 3.95 <= spacing / radius <= 4.05:
        return False
    axis = (axis_vector[0] / spacing, axis_vector[1] / spacing)
    normal = (-axis[1], axis[0])
    center = (
        (first_center[0] + second_center[0]) / 2.0,
        (first_center[1] + second_center[1]) / 2.0,
    )

    def project(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - center[0], point[1] - center[1]
        return (
            (dx * normal[0] + dy * normal[1]) / radius,
            (dx * axis[0] + dy * axis[1]) / radius,
        )

    projected_arcs = sorted(
        (
            (project(item["center"]), project(item["midpoint"]))
            for item in parsed_arcs
        ),
        key=lambda item: item[0][1],
    )
    expected_arc_positions = ((-2.0, -3.0), (2.0, 3.0))
    for (arc_center, arc_midpoint), (center_level, midpoint_level) in zip(
        projected_arcs, expected_arc_positions
    ):
        if (
            abs(arc_center[0]) > 0.05
            or abs(arc_center[1] - center_level) > 0.05
            or abs(arc_midpoint[0]) > 0.05
            or abs(arc_midpoint[1] - midpoint_level) > 0.05
        ):
            return False

    row_offsets = []
    for start, end in parsed_segments:
        local_start, local_end = project(start), project(end)
        dx = local_end[0] - local_start[0]
        dy = local_end[1] - local_start[1]
        length = math.hypot(dx, dy)
        if (
            not 3.95 <= length <= 4.05
            or abs(dy) / length < 0.995
            or abs(local_start[0] - local_end[0]) > 0.05
        ):
            return False
        levels = sorted((local_start[1], local_end[1]))
        if abs(levels[0] + 2.0) > 0.05 or abs(levels[1] - 2.0) > 0.05:
            return False
        row_offsets.append((local_start[0] + local_end[0]) / 2.0)
    row_offsets.sort()
    return bool(
        abs(row_offsets[0] + 1.0) <= 0.05
        and abs(row_offsets[1] - 1.0) <= 0.05
    )


def _has_vertical_zigzag_element_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the complete framed four-cell zigzag element geometrically.

    The frame supplies a local orthonormal coordinate system.  All remaining
    checks use frame-relative distances, so definition name, fingerprint,
    insertion rotation, reflection, translation, and uniform scale are absent
    from the decision.
    """

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if (
            int(histogram.get("LINE", 0)) != 12
            or int(histogram.get("LWPOLYLINE", 0)) != 1
            or sum(int(value) for value in histogram.values()) != 13
            or int(shape.get("text_count", 0)) != 0
            or shape.get("normalized_arcs")
            or shape.get("normalized_circles")
            or shape.get("normalized_closed_bulged_contacts")
            or shape.get("normalized_open_lwpolylines")
            or shape.get("normalized_inserts")
        ):
            return False
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        frames = shape.get("normalized_closed_straight_lwpolylines") or []
        if len(segments) != 12 or len(frames) != 1:
            return False
        vertices = [
            (float(point[0]), float(point[1]))
            for point in frames[0].get("vertices") or []
        ]
    except (KeyError, TypeError, ValueError):
        return False
    if len(vertices) != 4:
        return False

    edges = [
        (
            vertices[(index + 1) % 4][0] - vertices[index][0],
            vertices[(index + 1) % 4][1] - vertices[index][1],
        )
        for index in range(4)
    ]
    lengths = [math.hypot(*edge) for edge in edges]
    if min(lengths) <= 1e-9:
        return False
    ordered = sorted(lengths)
    frame_width = sum(ordered[:2]) / 2.0
    frame_length = sum(ordered[2:]) / 2.0
    if (
        not 2.74 <= frame_length / frame_width <= 2.86
        or abs(ordered[1] - ordered[0]) > frame_width * 0.02
        or abs(ordered[3] - ordered[2]) > frame_length * 0.02
    ):
        return False
    long_index = max(range(4), key=lengths.__getitem__)
    axis = (edges[long_index][0] / lengths[long_index], edges[long_index][1] / lengths[long_index])
    normal = (-axis[1], axis[0])
    center = (
        sum(point[0] for point in vertices) / 4.0,
        sum(point[1] for point in vertices) / 4.0,
    )

    # Require one true rectangle rather than accepting any four-sided frame.
    for index in range(4):
        left, right = edges[index], edges[(index + 1) % 4]
        denominator = lengths[index] * lengths[(index + 1) % 4]
        if abs(left[0] * right[0] + left[1] * right[1]) / denominator > 0.025:
            return False

    def project(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - center[0], point[1] - center[1]
        return (dx * axis[0] + dy * axis[1], dx * normal[0] + dy * normal[1])

    axis_tolerance = frame_length * 0.025
    normal_tolerance = frame_width * 0.04
    levels = [
        -frame_length / 2.0,
        -frame_length / 4.0,
        0.0,
        frame_length / 4.0,
        frame_length / 2.0,
    ]

    def level_index(value: float) -> int | None:
        index = min(range(5), key=lambda candidate: abs(value - levels[candidate]))
        return index if abs(value - levels[index]) <= axis_tolerance else None

    lead_sides: list[int] = []
    crossbar_levels: list[int] = []
    diagonal_intervals: dict[int, tuple[int, int]] = {}
    for start, end in segments:
        first, second = project(start), project(end)
        segment_length = math.dist(first, second)

        # Equal axial leads attach at the middle of opposite short frame edges.
        if abs(first[1]) <= normal_tolerance and abs(second[1]) <= normal_tolerance:
            inner, outer = sorted((first[0], second[0]), key=abs)
            side = 1 if outer > 0.0 else -1
            if (
                side * inner >= 0.0
                and abs(abs(inner) - frame_length / 2.0) <= axis_tolerance
                and 0.20 <= segment_length / frame_length <= 0.23
            ):
                lead_sides.append(side)
                continue

        first_level, second_level = level_index(first[0]), level_index(second[0])
        opposite_sides = (
            abs(abs(first[1]) - frame_width / 2.0) <= normal_tolerance
            and abs(abs(second[1]) - frame_width / 2.0) <= normal_tolerance
            and first[1] * second[1] < 0.0
        )
        if first_level is None or second_level is None or not opposite_sides:
            return False

        # Each of the three inner levels carries two coincident full-width bars.
        if first_level == second_level and first_level in {1, 2, 3}:
            if abs(segment_length - frame_width) > frame_width * 0.05:
                return False
            crossbar_levels.append(first_level)
            continue

        # Four equal-slope diagonals occupy the four adjacent level intervals.
        # At each inner level the duplicated full-width bar joins the end of
        # one diagonal to the opposite-side start of the next.
        low_index, high_index = sorted((first_level, second_level))
        if high_index - low_index != 1 or low_index in diagonal_intervals:
            return False
        low_point = first if first_level == low_index else second
        high_point = second if first_level == low_index else first
        diagonal_intervals[low_index] = (
            1 if low_point[1] > 0.0 else -1,
            1 if high_point[1] > 0.0 else -1,
        )

    if sorted(lead_sides) != [-1, 1] or Counter(crossbar_levels) != Counter({1: 2, 2: 2, 3: 2}):
        return False
    if set(diagonal_intervals) != {0, 1, 2, 3}:
        return False
    if any(low_side == high_side for low_side, high_side in diagonal_intervals.values()):
        return False
    return len(set(diagonal_intervals.values())) == 1


def _normalized_contact_count(shape: Mapping[str, Any]) -> int:
    return len(shape.get("normalized_closed_bulged_contacts") or [])


def _has_inline_rectangle_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """PWF168: rectangle, two collinear leads, and two equal contacts."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not (int(h.get("LINE", 0)) == 2 and int(h.get("LWPOLYLINE", 0)) == 3
            and int(h.get("ARC", 0)) == 0 and int(h.get("CIRCLE", 0)) == 0
            and int(shape.get("text_count", 0)) == 0
            and _normalized_contact_count(shape) == 2):
        return False
    frames = shape.get("normalized_closed_straight_lwpolylines") or []
    lines = shape.get("normalized_line_segments") or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if len(frames) != 1 or len(lines) != 2 or len(contacts) != 2:
        return False
    try:
        v = frames[0]["vertices"]
        lengths = [math.dist(v[i], v[(i + 1) % 4]) for i in range(4)]
        if len(v) != 4 or min(lengths) <= 0 or max(lengths) / min(lengths) > 3.0:
            return False
        radii = [float(c["radius"]) for c in contacts]
        if max(radii) / min(radii) > 1.04:
            return False
        centers = [(float(c["center"][0]), float(c["center"][1])) for c in contacts]
        axis = (centers[1][0] - centers[0][0], centers[1][1] - centers[0][1])
        span = math.hypot(*axis)
        if span <= 0 or not 7.0 <= span / max(radii) <= 24.0:
            return False
        normal = (-axis[1] / span, axis[0] / span)
        midpoint = ((centers[0][0] + centers[1][0]) / 2, (centers[0][1] + centers[1][1]) / 2)
        for line in lines:
            a, b = line["start"], line["end"]
            length = math.dist(a, b)
            center = ((float(a[0]) + float(b[0])) / 2, (float(a[1]) + float(b[1])) / 2)
            offset = abs((center[0] - midpoint[0]) * normal[0] + (center[1] - midpoint[1]) * normal[1])
            if not 0.20 <= length / span <= 0.40 or offset > max(radii) * .5:
                return False
        return True
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def _has_dual_row_arc_motif_topology(shape: Mapping[str, Any]) -> bool:
    """PWF209: four equal semicircles arranged as two parallel rows."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    arcs = shape.get("normalized_arcs") or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    lines = shape.get("normalized_line_segments") or []
    if (int(h.get("LINE", 0)) != 4 or int(h.get("ARC", 0)) != 4
            or int(h.get("LWPOLYLINE", 0)) != 4 or len(arcs) != 4
            or len(contacts) != 4 or len(lines) != 4
            or int(shape.get("text_count", 0)) != 0):
        return False

    def _levels(values: list[float], tolerance: float) -> list[tuple[float, int]]:
        groups: list[list[float]] = []
        for value in sorted(values):
            if not groups or abs(value - sum(groups[-1]) / len(groups[-1])) > tolerance:
                groups.append([value])
            else:
                groups[-1].append(value)
        return [(sum(group) / len(group), len(group)) for group in groups]

    try:
        radii = [float(a["radius"]) for a in arcs]
        sweeps = [abs(float(a.get("sweep_deg", a.get("sweep", 0)))) for a in arcs]
        if max(radii) / min(radii) > 1.04 or any(abs(s - 180) > 3 for s in sweeps):
            return False
        radius = sum(radii) / len(radii)
        tolerance = radius * .08
        arc_centers = [(float(a["center"][0]), float(a["center"][1])) for a in arcs]
        contact_centers = [
            (float(item["center"][0]), float(item["center"][1]))
            for item in contacts
        ]
        contact_radii = [float(item.get("chord_radius", item["radius"])) for item in contacts]
        if min(contact_radii) <= 0 or max(contact_radii) / min(contact_radii) > 1.04:
            return False
        arc_x = _levels([point[0] for point in arc_centers], tolerance)
        arc_y = _levels([point[1] for point in arc_centers], tolerance)
        contact_x = _levels([point[0] for point in contact_centers], tolerance)
        contact_y = _levels([point[1] for point in contact_centers], tolerance)
        if not all(
            len(levels) == 2 and [count for _, count in levels] == [2, 2]
            for levels in (arc_x, arc_y, contact_x, contact_y)
        ):
            return False
        ax0, ax1 = arc_x[0][0], arc_x[1][0]
        ay0, ay1 = arc_y[0][0], arc_y[1][0]
        cx0, cx1 = contact_x[0][0], contact_x[1][0]
        cy0, cy1 = contact_y[0][0], contact_y[1][0]
        if not (
            3.92 <= (ax1 - ax0) / radius <= 4.08
            and 1.92 <= (ay1 - ay0) / radius <= 2.08
            and 3.92 <= (ax0 - cx0) / radius <= 4.08
            and 3.92 <= (cx1 - ax1) / radius <= 4.08
            and 3.92 <= (cy1 - cy0) / radius <= 4.08
            and .92 <= (ay0 - cy0) / radius <= 1.08
            and .92 <= (cy1 - ay1) / radius <= 1.08
        ):
            return False
        expected_lines = (
            ((cx0, cy0), (ax0, cy0)),
            ((cx0, cy1), (ax0, cy1)),
            ((ax1, cy0), (cx1, cy0)),
            ((ax1, cy1), (cx1, cy1)),
        )
        actual_lines = []
        for item in lines:
            start = (float(item["start"][0]), float(item["start"][1]))
            end = (float(item["end"][0]), float(item["end"][1]))
            actual_lines.append((start, end) if start <= end else (end, start))
        for first, second in expected_lines:
            if not any(
                math.dist(first, start) <= tolerance and math.dist(second, end) <= tolerance
                for start, end in actual_lines
            ):
                return False
        for arc, (x, y) in zip(arcs, arc_centers):
            midpoint = arc.get("midpoint")
            if not midpoint:
                return False
            expected_x = x + radius if abs(x - ax0) <= tolerance else x - radius
            if math.dist((float(midpoint[0]), float(midpoint[1])), (expected_x, y)) > tolerance:
                return False
        return True
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _segments_match_similarity(
    rows: Sequence[Mapping[str, Any]],
    template: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    *,
    relative_tolerance: float = 0.025,
) -> bool:
    """Match a small undirected segment graph under rigid similarity.

    The comparison permits translation, rotation, uniform scale, and mirror,
    but no non-uniform stretch.  It is used only after an exact entity census
    so a familiar line ratio cannot suppress a larger unrelated symbol.
    """
    try:
        actual = [
            (
                (float(row["start"][0]), float(row["start"][1])),
                (float(row["end"][0]), float(row["end"][1])),
            )
            for row in rows
        ]
        if len(actual) != len(template) or not template:
            return False
        t0, t1 = template[0]
        tdx, tdy = t1[0] - t0[0], t1[1] - t0[1]
        tlen = math.hypot(tdx, tdy)
        if tlen <= 1e-12:
            return False
        tux, tuy = tdx / tlen, tdy / tlen
        tnx, tny = -tuy, tux

        for anchor in actual:
            for a0, a1 in (anchor, (anchor[1], anchor[0])):
                adx, ady = a1[0] - a0[0], a1[1] - a0[1]
                alen = math.hypot(adx, ady)
                if alen <= 1e-12:
                    continue
                scale = alen / tlen
                aux, auy = adx / alen, ady / alen
                anx, any_ = -auy, aux
                tolerance = max(1e-7, alen * relative_tolerance)
                for mirror in (1.0, -1.0):
                    transformed = []
                    for first, second in template:
                        pair = []
                        for point in (first, second):
                            rx, ry = point[0] - t0[0], point[1] - t0[1]
                            along = (rx * tux + ry * tuy) * scale
                            across = (rx * tnx + ry * tny) * scale * mirror
                            pair.append(
                                (
                                    a0[0] + along * aux + across * anx,
                                    a0[1] + along * auy + across * any_,
                                )
                            )
                        transformed.append((pair[0], pair[1]))
                    unmatched = list(actual)
                    for first, second in transformed:
                        match_index = next(
                            (
                                index
                                for index, (start, end) in enumerate(unmatched)
                                if (
                                    math.dist(first, start) <= tolerance
                                    and math.dist(second, end) <= tolerance
                                )
                                or (
                                    math.dist(first, end) <= tolerance
                                    and math.dist(second, start) <= tolerance
                                )
                            ),
                            None,
                        )
                        if match_index is None:
                            break
                        unmatched.pop(match_index)
                    else:
                        return not unmatched
        return False
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_framed_inline_noport_topology(shape: Mapping[str, Any]) -> bool:
    """Central rectangle with two opposite collinear leads, no contacts."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    frames = shape.get("normalized_closed_straight_lwpolylines") or []
    lines = shape.get("normalized_line_segments") or []
    if not (
        int(h.get("LINE", 0)) == 2
        and int(h.get("LWPOLYLINE", 0)) == 1
        and sum(int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "HATCH", "INSERT")) == 0
        and int(shape.get("text_count", 0)) == 0
        and len(frames) == 1
        and len(lines) == 2
        and not (shape.get("normalized_closed_bulged_contacts") or [])
    ):
        return False
    try:
        vertices = [tuple(map(float, point[:2])) for point in frames[0]["vertices"]]
        if len(vertices) != 4:
            return False
        edges = [
            (vertices[index], vertices[(index + 1) % 4]) for index in range(4)
        ]
        lengths = [math.dist(*edge) for edge in edges]
        short, long = min(lengths), max(lengths)
        if short <= 1e-12 or not 2.55 <= long / short <= 2.80:
            return False
        long_edges = [edge for edge, length in zip(edges, lengths) if length >= long * 0.98]
        if len(long_edges) != 2:
            return False
        axis = (
            (long_edges[0][1][0] - long_edges[0][0][0]) / long,
            (long_edges[0][1][1] - long_edges[0][0][1]) / long,
        )
        normal = (-axis[1], axis[0])
        center = (
            sum(point[0] for point in vertices) / 4.0,
            sum(point[1] for point in vertices) / 4.0,
        )
        side_signs = []
        for row in lines:
            start = tuple(map(float, row["start"][:2]))
            end = tuple(map(float, row["end"][:2]))
            vector = (end[0] - start[0], end[1] - start[1])
            length = math.hypot(*vector)
            midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            if not 0.47 <= length / long <= 0.53:
                return False
            if abs(vector[0] * normal[0] + vector[1] * normal[1]) > long * 0.025:
                return False
            if abs((midpoint[0] - center[0]) * normal[0] + (midpoint[1] - center[1]) * normal[1]) > short * 0.08:
                return False
            axial = (midpoint[0] - center[0]) * axis[0] + (midpoint[1] - center[1]) * axis[1]
            if abs(axial) < long * 0.65:
                return False
            side_signs.append(1 if axial > 0 else -1)
        return sorted(side_signs) == [-1, 1]
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_four_line_open_switch_ignore_topology(shape: Mapping[str, Any]) -> bool:
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    lines = shape.get("normalized_line_segments") or []
    template = (
        ((3.0, 0.0), (2.0, 0.0)),
        ((0.0, 0.0), (1.0, 0.0)),
        ((1.0, 0.0), (1.0, 0.5)),
        ((2.0, 0.0), (0.75, 0.5)),
    )
    return (
        int(h.get("LINE", 0)) == 4
        and sum(int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "LWPOLYLINE", "HATCH", "INSERT")) == 0
        and int(shape.get("text_count", 0)) == 0
        and _segments_match_similarity(lines, template)
    )


def _has_five_line_vertical_switch_ignore_topology(shape: Mapping[str, Any]) -> bool:
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    lines = shape.get("normalized_line_segments") or []
    template = (
        ((0.75, 0.0), (0.75, 1.0)),
        ((0.0, 3.0), (0.0, 2.0)),
        ((0.0, 2.0), (0.5, 2.0)),
        ((0.75, 1.0), (0.25, 2.25)),
        ((0.75, 3.0), (0.75, 2.0)),
    )
    return (
        int(h.get("LINE", 0)) == 5
        and sum(int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "LWPOLYLINE", "HATCH", "INSERT")) == 0
        and int(shape.get("text_count", 0)) == 0
        and _segments_match_similarity(lines, template)
    )


def _has_two_contact_bulged_switch_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Two equal contacts plus three open bulged paths (PWF26 family)."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    paths = shape.get("normalized_open_lwpolylines") or []
    if not (
        int(h.get("LWPOLYLINE", 0)) == 5
        and sum(int(h.get(key, 0)) for key in ("LINE", "ARC", "CIRCLE", "HATCH", "INSERT")) == 0
        and int(shape.get("text_count", 0)) == 0
        and len(contacts) == 2
        and len(paths) == 3
        and sorted(len(path.get("vertices") or []) for path in paths) == [2, 3, 3]
    ):
        return False
    try:
        centers = [tuple(map(float, item["center"][:2])) for item in contacts]
        radii = [float(item.get("chord_radius", item["radius"])) for item in contacts]
        span = math.dist(*centers)
        if min(radii) <= 0 or max(radii) / min(radii) > 1.04 or not 19.5 <= span / (sum(radii) / 2) <= 20.5:
            return False
        bulges = sorted(
            round(abs(float(vertex.get("bulge", 0.0))), 3)
            for path in paths
            for vertex in path.get("vertices") or []
            if abs(float(vertex.get("bulge", 0.0))) > 1e-6
        )
        if bulges != [1.0, 1.0, 2.414]:
            return False
        axis = ((centers[1][0] - centers[0][0]) / span, (centers[1][1] - centers[0][1]) / span)
        base_normal = (-axis[1], axis[0])
        expected = (
            ((-1 / 6, 1 / 6), (7 / 6, 1 / 6)),
            ((0.5, 1 / 6), (1.0, 1 / 6), (1.0, 0.0)),
            ((0.0, 0.0), (0.0, 1 / 6), (0.5, 1 / 6)),
        )
        for swap in (False, True):
            origin = centers[1] if swap else centers[0]
            along = (-axis[0], -axis[1]) if swap else axis
            for normal_sign in (1.0, -1.0):
                normal = (base_normal[0] * normal_sign, base_normal[1] * normal_sign)
                actual_paths = []
                for path in paths:
                    points = []
                    for vertex in path["vertices"]:
                        point = vertex["point"]
                        dx, dy = float(point[0]) - origin[0], float(point[1]) - origin[1]
                        points.append((dx * along[0] / span + dy * along[1] / span,
                                       dx * normal[0] / span + dy * normal[1] / span))
                    actual_paths.append(points)
                unmatched = list(actual_paths)
                for expected_path in expected:
                    index = next((i for i, points in enumerate(unmatched)
                                  if len(points) == len(expected_path)
                                  and (all(math.dist(a, b) <= .025 for a, b in zip(points, expected_path))
                                       or all(math.dist(a, b) <= .025 for a, b in zip(reversed(points), expected_path)))), None)
                    if index is None:
                        break
                    unmatched.pop(index)
                else:
                    return not unmatched
        return False
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_dense_nkp_panel_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Dense J1..J6/L/N/E panel with orthogonal 6+3 contact grids."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    labels = {str(value).strip().upper() for value in shape.get("text_values") or []}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if not (
        int(h.get("LINE", 0)) == 105
        and int(h.get("LWPOLYLINE", 0)) == 17
        and int(h.get("TEXT", 0)) == 9
        and sum(int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "HATCH", "INSERT")) == 0
        and labels == {"J1", "J2", "J3", "J4", "J5", "J6", "L", "N", "E"}
        and len(contacts) == 9
        and len(shape.get("normalized_closed_straight_lwpolylines") or []) == 7
        and len(shape.get("normalized_open_lwpolylines") or []) == 1
        and len(shape.get("normalized_open_lwpolyline_segments") or []) == 3
        and int(shape.get("parallel_line_group_max", 0)) >= 29
        and 6.35 <= float(shape.get("oriented_aspect_ratio") or 0.0) <= 6.70
    ):
        return False
    try:
        points = [tuple(map(float, item["center"][:2])) for item in contacts]
        radii = [float(item.get("chord_radius", item["radius"])) for item in contacts]
        if min(radii) <= 0 or max(radii) / min(radii) > 1.04:
            return False

        def regular_collinear(group: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], float] | None:
            first, last = max(combinations(group, 2), key=lambda pair: math.dist(*pair))
            span = math.dist(first, last)
            if span <= 1e-12:
                return None
            axis = ((last[0] - first[0]) / span, (last[1] - first[1]) / span)
            projections = sorted((point[0] - first[0]) * axis[0] + (point[1] - first[1]) * axis[1] for point in group)
            offsets = [abs((point[0] - first[0]) * -axis[1] + (point[1] - first[1]) * axis[0]) for point in group]
            gaps = [second - first_ for first_, second in zip(projections, projections[1:])]
            if max(offsets) > span * .005 or min(gaps) <= 0 or max(gaps) / min(gaps) > 1.04:
                return None
            return axis, sum(gaps) / len(gaps)

        for indexes in combinations(range(9), 6):
            first_group = [points[index] for index in indexes]
            second_group = [points[index] for index in range(9) if index not in indexes]
            first_line = regular_collinear(first_group)
            second_line = regular_collinear(second_group)
            if first_line and second_line and abs(first_line[0][0] * second_line[0][0] + first_line[0][1] * second_line[0][1]) <= .03:
                return True
        return False
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_switch_class_ignore_topology(shape: Mapping[str, Any]) -> tuple[str, str] | None:
    """Strict, name/fingerprint-free contracts for the safe switch subclasses.

    These checks intentionally use primitive counts plus normalized relative
    geometry.  The two PWF166 variants are separate rules so equal counts or
    names can never cross-match.
    """
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    def n(key: str) -> int:
        try: return int(h.get(key, 0))
        except (TypeError, ValueError): return 0
    if _has_dense_nkp_panel_ignore_topology(shape):
        return ("dense-j1-j6-lne-panel-ignore-v1", "dense-j1-j6-lne-panel-ignore-v1")
    if int(shape.get("text_count", 0)) != 0:
        return None
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    lines = shape.get("normalized_line_segments") or []
    if (
        n("LINE") == 1
        and n("LWPOLYLINE") in {4, 6}
        and len(contacts) == n("LWPOLYLINE")
        and len(lines) == 1
    ):
        try:
            line_start = (float(lines[0]["start"][0]), float(lines[0]["start"][1]))
            line_end = (float(lines[0]["end"][0]), float(lines[0]["end"][1]))
            line_length = math.dist(line_start, line_end)
            if line_length <= 1e-9:
                return None
            axis = (
                (line_end[0] - line_start[0]) / line_length,
                (line_end[1] - line_start[1]) / line_length,
            )
            normal = (-axis[1], axis[0])
            centers = [
                (float(item["center"][0]), float(item["center"][1]))
                for item in contacts
            ]
            radii = [float(item.get("chord_radius", item["radius"])) for item in contacts]
            if min(radii) <= 0 or max(radii) / min(radii) > 1.04:
                return None
            origin = centers[0]
            axial = [
                (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]
                for point in centers
            ]
            normal_offsets = [
                abs((point[0] - origin[0]) * normal[0] + (point[1] - origin[1]) * normal[1])
                for point in centers
            ]
            span = max(axial) - min(axial)
            radius = sum(radii) / len(radii)
            if (
                span <= 1e-9
                or max(normal_offsets) > radius * .12
                or not 12.3 <= span / radius <= 12.7
                or not .39 <= line_length / span <= .41
            ):
                return None
            levels = sorted(round((value - min(axial)) / span, 3) for value in axial)
            endpoint_levels = sorted(
                round(
                    (((point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]) - min(axial))
                    / span,
                    3,
                )
                for point in (line_start, line_end)
            )
            if len(contacts) == 6:
                valid_levels = ([0.0, 0.0, 0.0, 0.6, 0.8, 1.0], [0.0, 0.2, 0.4, 1.0, 1.0, 1.0])
                valid_lines = ([0.6, 1.0], [0.0, 0.4])
                if levels in valid_levels and endpoint_levels in valid_lines:
                    return ("vertical-six-contact-stack-ignore-v1", "vertical-six-contact-stack-ignore-v1")
            else:
                valid_levels = ([0.0, 0.0, 0.6, 1.0], [0.0, 0.4, 1.0, 1.0])
                valid_lines = ([0.6, 1.0], [0.0, 0.4])
                if levels in valid_levels and endpoint_levels in valid_lines:
                    return ("vertical-four-contact-stack-ignore-v1", "vertical-four-contact-stack-ignore-v1")
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            return None
    # PWF265: the frame and two bulged contacts are mandatory; all four hatch
    # regions are part of the proof, not an optional visual hint.
    if (n("CIRCLE") == 1 and n("LINE") == 5 and n("LWPOLYLINE") == 4
            and n("HATCH") == 4 and len(contacts) == 2
            and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2):
        return ("circle-line-five-bulged-contact-frame-hatch-v1", "circle-line-five-bulged-contact-frame-hatch-v1")
    if _has_framed_inline_noport_topology(shape):
        return ("framed-inline-noport-ignore-v1", "framed-inline-noport-ignore-v1")
    if _has_four_line_open_switch_ignore_topology(shape):
        return ("four-line-actuated-open-switch-ignore-v1", "four-line-actuated-open-switch-ignore-v1")
    if _has_two_contact_bulged_switch_ignore_topology(shape):
        return ("two-contact-three-open-bulged-path-ignore-v1", "two-contact-three-open-bulged-path-ignore-v1")
    if _has_five_line_vertical_switch_ignore_topology(shape):
        return ("five-line-vertical-changeover-ignore-v1", "five-line-vertical-changeover-ignore-v1")
    return None


def _has_pwf163_switch_topology(shape: Mapping[str, Any]) -> bool:
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not (int(h.get("LINE", 0)) == 3 and int(h.get("ARC", 0)) == 0
            and int(h.get("LWPOLYLINE", 0)) == 4
            and _normalized_contact_count(shape) == 4
            and int(shape.get("text_count", 0)) == 0):
        return False
    lines = shape.get("normalized_line_segments") or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    points = [(float(c["center"][0]), float(c["center"][1])) for c in contacts]
    span = math.dist(min(points), max(points)) if points else 0.0
    lengths = [math.dist(s["start"], s["end"]) for s in lines]
    rows = sorted(points, key=lambda p: p[1])
    return (span > 0 and max(float(c["radius"]) for c in contacts) / span < .15
            and len(lengths) == 3 and max(lengths) / span > .18
            and max(p[1] for p in points) - min(p[1] for p in points) > span * .10
            and abs(rows[0][1] - rows[1][1]) < span * .08
            and abs(rows[2][1] - rows[3][1]) < span * .08)


def _has_pwf175_two_port_topology(shape: Mapping[str, Any]) -> bool:
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    circles = shape.get("normalized_circles") or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    return (int(h.get("LINE", 0)) == 2 and int(h.get("CIRCLE", 0)) == 2
            and int(h.get("ARC", 0)) == 0 and int(h.get("LWPOLYLINE", 0)) == 2
            and len(circles) == len(contacts) == 2
            and int(shape.get("text_count", 0)) == 0
            and abs(float(shape.get("oriented_aspect_ratio") or 0)) >= 2.0
            and abs(float(circles[0]["center"][1]) - float(circles[1]["center"][1])) < .2 * max(float(circles[0]["radius"]), float(circles[1]["radius"])))


def _match_confirmed_ignore_geometry_family(
    shape: Mapping[str, Any],
    *,
    port_count: int,
    aspect_ratio: float,
) -> tuple[str, str, float] | None:
    """Match confirmed non-connective families using normalized geometry only."""

    primitive_histogram = shape.get("primitive_histogram")
    entity_histogram = shape.get("entity_histogram")
    primitive_histogram = (
        primitive_histogram if isinstance(primitive_histogram, Mapping) else {}
    )
    entity_histogram = entity_histogram if isinstance(entity_histogram, Mapping) else {}

    def count(name: str) -> int:
        try:
            return int(entity_histogram.get(name, primitive_histogram.get(name, 0)))
        except (TypeError, ValueError):
            return 0

    if _is_three_contact_selector_switch_geometry(shape, port_count=port_count):
        return (
            "electrical.nonconnective_switch_class_ignore.v1",
            "three-radial-contact-selector-slash-ignore-v1",
            0.99,
        )
    actuated_switch_rule = _actuated_switch_signature_rule(
        shape, port_count=port_count
    )
    if actuated_switch_rule:
        return (
            "electrical.nonconnective_switch_class_ignore.v1",
            actuated_switch_rule,
            0.99,
        )
    if _is_line_only_actuated_switch_geometry(shape, port_count=port_count):
        return (
            "electrical.nonconnective_switch_class_ignore.v1",
            "eight-line-duplicated-blade-actuator-switch-ignore-v1",
            0.99,
        )
    if _is_rectangular_diagonal_mechanism_ignore_geometry(
        shape, port_count=port_count
    ):
        return (
            "electrical.nonconnective_switch_class_ignore.v1",
            "rectangular-diagonal-mechanism-ignore-v1",
            0.99,
        )
    if _is_remote_interface_marker_ignore_geometry(shape, port_count=port_count):
        return (
            "communication.remote_interface_marker_ignored.v1",
            "contact-led-round-remote-interface-marker-v1",
            0.99,
        )
    if _is_optical_st_bracket_marker_ignore_geometry(shape, port_count=port_count):
        return (
            "communication.optical_st_port_ignored.v1",
            "two-contact-parenthesis-optical-marker-v1",
            0.99,
        )
    if _is_two_arc_capsule_routing_ignore_geometry(shape, port_count=port_count):
        return (
            "line_break.non_connective.v1",
            "two-semicircle-two-line-routing-capsule-v1",
            0.99,
        )

    # These four contracts are deliberately geometry-only.  Exact fingerprints
    # above provide provenance and human status; they are never consulted here.
    if count("LINE") == 2 and count("LWPOLYLINE") == 3 and _has_inline_rectangle_ignore_topology(shape):
        return ("electrical.nonconnective_inline_rectangle_ignored.v1",
                "inline-rectangle-two-collinear-leads-v1", 0.99)
    if _has_dual_row_arc_motif_topology(shape):
        return ("electrical.nonconnective_dual_row_arc_motif_ignored.v1",
                "dual-row-four-equal-semicircle-arc-wire-v1", 0.99)
    if _has_pwf172_led_arrow_ignore_topology(shape):
        return ("electrical.nonconnective_led_arrow_ignored.v1",
                "pwf172-led-diode-arrow-complete-v1", 0.99)
    if _has_pwf216_narrow_frame_ignore_topology(shape):
        return ("electrical.nonconnective_narrow_frame_ignored.v1",
                "pwf216-narrow-frame-slanted-base-complete-v1", 0.99)
    if _has_pwf163_switch_topology(shape):
        return ("switch.open.v1", "three-line-four-contact-open-switch-v1", 0.98)
    if _has_pwf175_two_port_topology(shape):
        return ("component.external_strip_two_port.v1",
                "named-isolated-two-circle-two-port-v1", 0.98)

    switch_match = _has_switch_class_ignore_topology(shape)
    if switch_match is not None:
        rule_id, _ = switch_match
        family_id = (
            "electrical.ground_symbol_ignored.v1"
            if rule_id in {
                "vertical-six-contact-stack-ignore-v1",
                "vertical-four-contact-stack-ignore-v1",
            }
            else "electrical.nonconnective_switch_class_ignore.v1"
        )
        return (family_id, rule_id, 0.99)

    arc_radii = [
        float(value)
        for value in shape.get("arc_radii") or []
        if isinstance(value, (int, float)) and float(value) > 0.0
    ]
    circle_count = len(shape.get("circle_radii") or [])
    short_side = min(float(shape.get("width") or 0.0), float(shape.get("height") or 0.0))
    normalized_arc_radius = (
        sum(arc_radii) / len(arc_radii) / short_side
        if arc_radii and short_side > 1e-9
        else 0.0
    )
    oriented_short_side = min(
        float(shape.get("oriented_width") or 0.0),
        float(shape.get("oriented_height") or 0.0),
    )
    oriented_aspect_ratio = float(shape.get("oriented_aspect_ratio") or 0.0)
    oriented_normalized_arc_radius = (
        sum(arc_radii) / len(arc_radii) / oriented_short_side
        if arc_radii and oriented_short_side > 1e-9
        else 0.0
    )

    text_values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    communication_panel_labels = {
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
        "ST", "1T", "1R", "P+", "P-", "TX", "RX", "GND",
    }
    circle_radii = sorted(
        float(value)
        for value in shape.get("circle_radii") or []
        if isinstance(value, (int, float)) and float(value) > 0.0
    )
    paired_optical_circle_radii = bool(
        len(circle_radii) == 4
        and abs(circle_radii[1] - circle_radii[0]) <= circle_radii[0] * 0.03
        and abs(circle_radii[3] - circle_radii[2]) <= circle_radii[2] * 0.03
        and 1.15 <= circle_radii[2] / circle_radii[0] <= 1.5
    )

    if (
        2 <= port_count <= 4
        and _has_vertical_zigzag_element_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_vertical_zigzag_element_ignored.v1",
            "narrow-frame-four-cell-zigzag-v1",
            0.99,
        )

    if (
        port_count in {2, 3, 4}
        and count("INSERT") == 4
        and count("LINE") == 8
        and count("LWPOLYLINE") == 3
        and count("ARC") == 0
        and count("CIRCLE") == 0
        and count("HATCH") == 0
        and count("POLYLINE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 3
        and _has_grounded_three_row_cb_panel_topology(shape)
    ):
        return (
            "electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1",
            "grounded-three-row-repeated-mechanism-panel-v1",
            0.99,
        )

    if (
        port_count in {2, 3, 4}
        and count("ARC") == 2
        and count("LINE") == 2
        and count("LWPOLYLINE") == 0
        and count("POLYLINE") == 0
        and count("CIRCLE") == 0
        and count("HATCH") == 0
        and count("INSERT") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and _has_closed_cable_sleeve_topology(shape)
    ):
        return (
            "non_electrical.cable_sleeve_ignored.v1",
            "closed-opposed-semicircle-cable-sleeve-v1",
            0.99,
        )

    if _has_dgicom_8g12_equipment_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "dgicom-8g12-40-circle-complete-panel-v1",
            0.99,
        )

    if _has_wyd_communication_equipment_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "wyd-8com-12lan-complete-panel-v1",
            0.99,
        )

    # Wide NGFW firewall face with ETH/P sockets, USB indicators, paired
    # optical circles and dual power-terminal drawings.
    if _has_firewall_eth_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "firewall-eth-usb-optical-power-panel-v1",
            0.99,
        )

    # Enclosed HYKL 4x2 IN/OUT interface face.  Circles and outward contacts
    # are recognition evidence only; the whole panel is electrically ignored.
    if _has_hykl_dual_row_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "dual-row-pe-tx-rx-interface-panel-v1",
            0.99,
        )

    # Compact 8-GE / 2-GX switch face.  Complete connector arrays, optical
    # circle grid and native panel labels are required together.
    if _has_compact_ge_gx_switch_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "compact-ge-gx-power-switch-panel-v1",
            0.99,
        )

    if _has_dgicom3000_4gx8ge_hv_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "dgicom3000-4gx8ge-hv-complete-panel-v1",
            0.99,
        )

    # Wide 24-GE / 4-GX switch face.  Text arrays establish the equipment
    # semantics while the repeated square cells and alternating optical-circle
    # pitch establish the geometry.  The conjunction is intentionally strict:
    # neither a dense terminal strip nor a text-only panel may inherit IGNORE.
    if _has_wide_ge_gx_switch_panel_topology(shape, port_count=port_count):
        return (
            "communication.equipment_panel_ignored.v1",
            "wide-ge-gx-power-switch-panel-v1",
            0.99,
        )

    # Tall communication-equipment panel with six native COM sections, power
    # annotations, and a paired optical ST motif.  The semantic anchors prevent
    # similarly dense terminal strips from inheriting this whole-region IGNORE
    # policy; dimensions and circle ratios remain uniform-scale invariant.
    if (
        port_count == 2
        and not arc_radii
        and paired_optical_circle_radii
        and communication_panel_labels <= text_values
        and {"+/L", "-/N"} <= text_values
        and 20 <= count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") <= 40
        and 15 <= count("LINE") <= 30
        and 15 <= count("LWPOLYLINE") <= 35
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) >= 12
        and int(shape.get("parallel_line_group_max", 0)) >= 12
        and 5.0 <= max(aspect_ratio, oriented_aspect_ratio) <= 9.0
    ):
        return (
            "communication.equipment_panel_ignored.v1",
            "tall-six-com-power-optical-panel-v1",
            0.99,
        )

    if (
        port_count >= 4
        and count("TEXT") + count("ATTDEF") >= 20
        and count("LINE") + count("LWPOLYLINE") >= 30
        and max(float(shape.get("width") or 0.0), float(shape.get("height") or 0.0))
        >= 100.0
    ):
        return (
            "non_electrical.drawing_metadata.v1",
            "large-text-dense-drawing-metadata-v1",
            0.99,
        )
    if (
        _has_ethernet_lan_port_topology(shape)
    ):
        return (
            "communication.ethernet_port_ignored.v1",
            "ethernet-lan-wide-contact-body-topology-v1",
            0.98,
        )
    if (
        port_count in {4, 5}
        and count("TEXT") == 2
        and count("LWPOLYLINE") in {2, 3}
        and count("LINE") == 0
        and not arc_radii
        and circle_count == 0
        and 1.0 <= aspect_ratio <= 1.4
    ):
        return (
            "communication.ethernet_port_ignored.v1",
            "confirmed-ethernet-port-geometry-v1",
            0.98,
        )
    if (
        port_count == 2
        and len(arc_radii) == 1
        and circle_count == 0
        and count("LINE") == 1
        and count("LWPOLYLINE") == 2
        and count("TEXT") == 0
        and 1.6 <= aspect_ratio <= 2.1
        and 0.25 <= normalized_arc_radius <= 0.35
    ):
        return (
            "communication.optical_st_port_ignored.v1",
            "confirmed-optical-st-port-geometry-v1",
            0.98,
        )

    if (
        port_count == 2
        and count("LINE") == 2
        and count("ARC") == 1
        and count("LWPOLYLINE") == 0
        and count("POLYLINE") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and _has_wire_crossover_jump_topology(shape)
    ):
        return (
            "wire.crossover_jump.v1",
            "line-arc-line-crossover-jump-v1",
            0.99,
        )

    if (
        port_count in {2, 4}
        and len(arc_radii) == 4
        and max(arc_radii) - min(arc_radii) <= sum(arc_radii) / 4.0 * 0.03
        and circle_count == 0
        and count("LINE") == 10
        and count("LWPOLYLINE") == 0
        and count("POLYLINE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and 2.1 <= oriented_aspect_ratio <= 2.4
        and 0.17 <= oriented_normalized_arc_radius <= 0.21
        and int(shape.get("parallel_line_group_max", 0)) >= 9
        and _has_four_coil_topology(shape)
    ):
        return (
            "electrical.nonconnective_four_coil_ignored.v1",
            "four-equal-semicircle-coil-grid-v1",
            0.98,
        )

    if (
        port_count in {1, 2, 3, 4}
        and len(arc_radii) == 12
        and count("LINE") == 26
        and count("LWPOLYLINE") == 4
        and count("POLYLINE") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 4
        and _has_repeated_three_row_coil_panel_topology(shape)
    ):
        return (
            "electrical.nonconnective_repeated_coil_panel_ignored.v1",
            "repeated-three-row-semicircle-panel-v1",
            0.99,
        )

    if (
        port_count in {2, 3, 4}
        and count("LINE") == 2
        and count("CIRCLE") == 1
        and count("LWPOLYLINE") == 2
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("HATCH") == 0
        and count("INSERT") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_crossed_circle_opposed_contacts_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_crossed_circle_marker_ignored.v1",
            "crossed-circle-opposed-contact-regions-v1",
            0.99,
        )

    if (
        port_count in {2, 3, 4}
        and count("LINE") == 7
        and count("LWPOLYLINE") == 2
        and count("POLYLINE") == 0
        and count("CIRCLE") == 0
        and count("ARC") == 0
        and count("HATCH") == 0
        and count("INSERT") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_actuated_open_switch_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_actuated_open_switch_ignored.v1",
            "two-contact-actuated-open-switch-v1",
            0.99,
        )

    if (
        port_count in {1, 2, 3, 4}
        and count("LWPOLYLINE") == 2
        and count("LINE") == 0
        and count("POLYLINE") == 0
        and count("CIRCLE") == 0
        and count("ARC") == 0
        and count("HATCH") == 0
        and count("INSERT") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 1
        and _has_wide_contact_cap_marker_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_wide_contact_cap_marker_ignored.v1",
            "straight-wide-two-contact-cap-marker-v1",
            0.99,
        )

    if (
        port_count in {2, 3, 4}
        and count("LINE") == 10
        and count("LWPOLYLINE") == 6
        and count("CIRCLE") == 2
        and count("HATCH") == 8
        and count("ARC") == 0
        and count("POLYLINE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_dual_row_hatched_signal_panel_topology(shape)
    ):
        return (
            "electrical.nonconnective_dual_row_signal_panel_ignored.v1",
            "dual-row-hatched-circle-panel-v1",
            0.99,
        )
    if (
        port_count in {2, 3, 4}
        and count("LINE") == 2
        and count("CIRCLE") == 1
        and count("HATCH") == 1
        and count("LWPOLYLINE") == 1
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 1
        and 1.6 <= max(aspect_ratio, oriented_aspect_ratio) <= 1.9
        and _has_circle_contact_marker_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_circle_contact_marker_ignored.v1",
            "diameter-circle-offset-contact-marker-v1",
            0.99,
        )

    # Shared stepped non-connective geometry.  Human-exact policies refine
    # this reflection-equivalent shape to either the right-side DZB marker or
    # the left-side ground symbol.  Geometry alone cannot truthfully infer
    # which semantic label applies after reflection, but it can safely prove
    # the common zero-port/non-connective behavior.
    # Three parallel stepped bars are each
    # duplicated by an open two-point polyline; the longest bar is attached at
    # its centre to a doubled orthogonal stem and a half-length side lead.
    # The topology helper uses relative vectors/distances only, so uniform
    # scale, rotation, and reflection do not affect the decision.
    if (
        port_count in {1, 2}
        and count("LINE") == 6
        and count("LWPOLYLINE") == 3
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and (
            (
                0.9 <= oriented_aspect_ratio <= 1.15
                and _has_dzb_right_marker_topology(shape)
            )
            or _has_repeated_stepped_ground_topology(shape)
        )
    ):
        return (
            "electrical.nonconnective_stepped_marker_ignored.v1",
            "stepped-duplicate-bar-nonconnective-v1",
            0.98,
        )

    # Circled ground glyph: three centred, equally stepped bars with 1:.75:.5
    # relative lengths; the longest bar midpoint joins a perpendicular lead
    # ending in a closed round contact, and one larger circle encloses the
    # complete motif.  The helper works in a local bar/lead frame, so rotation,
    # reflection, translation, and uniform scale do not affect the decision.
    if (
        port_count in {1, 2, 3, 4, 5}
        and count("LINE") == 4
        and count("CIRCLE") == 1
        and count("LWPOLYLINE") == 1
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("HATCH") == 0
        and count("INSERT") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 1
        and _has_circled_stepped_ground_topology(shape)
    ):
        return (
            "electrical.ground_symbol_ignored.v1",
            "circled-stepped-bar-ground-contact-v1",
            0.99,
        )

    # Contact-led GND glyph: three increasingly long stepped bars are each
    # duplicated by an open two-point polyline; the longest bar midpoint joins
    # a perpendicular lead ending in one closed round contact.  Relative
    # topology makes the rule invariant to rotation, reflection, and scale.
    if (
        port_count in {1, 2, 3, 4, 5}
        and count("LINE") == 4
        and count("LWPOLYLINE") == 4
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 1
        and _has_contact_led_stepped_ground_topology(shape)
    ):
        return (
            "electrical.ground_symbol_ignored.v1",
            "ground-symbol-contact-led-stepped-bars-v1",
            0.98,
        )

    # Three-lead boxed graphic with a bottom nested rectangle and its corner
    # diagonal.  Geometry is matched by relative rectangle dimensions,
    # centres, line directions, and attachment loci rather than CAD axes.
    if (
        port_count in {2, 3}
        and count("LINE") == 4
        and count("LWPOLYLINE") == 2
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 0
        and _has_three_lead_box_topology(shape)
    ):
        return (
            "electrical.nonconnective_three_lead_box_ignored.v1",
            "nested-box-three-lead-diagonal-v1",
            0.98,
        )

    # Ground symbol: one lead and three progressively shorter, mutually
    # parallel bars, plus a closed bulged LWPOLYLINE contact.  All quantities
    # below are normalized, so rotation and uniform scale do not matter.
    if (
        port_count in {4, 5}
        and count("LINE") == 4
        and count("LWPOLYLINE") == 1
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("CIRCLE") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 1
        and int(shape.get("parallel_line_group_max", 0)) >= 3
        and len(shape.get("normalized_line_lengths") or []) == 4
        and _has_ground_symbol_topology(shape)
    ):
        return (
            "electrical.ground_symbol_ignored.v1",
            "ground-symbol-four-line-bulged-contact-v1",
            0.98,
        )

    # Diodes are graphics in this audit model.  Counts and aspect ratio are
    # only a prefilter; the normalized topology guards against same-count
    # terminals, switches, and arbitrary hatch graphics.
    if (
        port_count == 2 and count("LINE") == 5 and count("LWPOLYLINE") == 2
        and count("HATCH") == 0 and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and not arc_radii and circle_count == 0 and 1.0 <= aspect_ratio <= 2.3
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_bare_diode_topology(shape)
    ):
        return ("electrical.diode_symbol_ignored.v1", "bare-diode-triangle-bar-leads-v1", 0.98)
    if (
        port_count >= 3 and count("HATCH") == 2 and count("LINE") == 13
        and count("LWPOLYLINE") == 3 and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and not arc_radii and circle_count == 0 and 1.0 <= aspect_ratio <= 1.5
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_boxed_diode_topology(shape)
    ):
        return ("electrical.diode_symbol_ignored.v1", "boxed-diode-repeated-topology-v1", 0.98)

    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and count("LINE") == 1
        and 5 <= count("LWPOLYLINE") <= 7
        and 2.0 <= aspect_ratio <= 2.8
    ):
        return (
            "non_electrical.numeric_text.v1",
            "confirmed-numeric-text-geometry-v1",
            0.95,
        )
    if (
        port_count in {2, 3, 4}
        and count("LINE") == 6
        and count("CIRCLE") == 1
        and count("HATCH") == 2
        and count("LWPOLYLINE") == 0
        and count("POLYLINE") == 0
        and count("ARC") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and _has_inline_indicator_ignore_topology(shape)
    ):
        return (
            "electrical.nonconnective_inline_indicator_ignored.v1",
            "hatched-circle-inline-indicator-v1",
            0.99,
        )
    if (
        port_count in {2, 3, 4}
        and not arc_radii
        and circle_count == 0
        and count("LINE") == 2
        and count("LWPOLYLINE") == 5
        and count("POLYLINE") == 0
        and count("HATCH") == 0
        and count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 2
        and _has_crossed_two_contact_open_switch_topology(shape)
    ):
        return (
            "switch.open.v1",
            "crossed-two-contact-open-switch-v1",
            0.99,
        )
    if (
        port_count >= 3
        and count("HATCH") >= 1
        and 10 <= count("LINE") <= 16
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.0 <= aspect_ratio <= 1.4
    ):
        return (
            "non_electrical.graphic.v1",
            "confirmed-hatched-nonconnective-geometry-v1",
            0.96,
        )
    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and 3 <= count("LINE") <= 4
        and count("LWPOLYLINE") == 2
        and 5.5 <= aspect_ratio <= 7.5
    ):
        return ("switch.open.v1", "confirmed-open-switch-geometry-v1", 0.97)
    if (
        port_count >= 4
        and count("TEXT") >= 2
        and count("LINE") <= 2
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.0 <= aspect_ratio <= 1.3
    ):
        return (
            "non_electrical.functional_graphic.v1",
            "confirmed-functional-graphic-geometry-v1",
            0.96,
        )
    if (
        port_count == 2
        and len(arc_radii) == 2
        and count("LINE") in {2, 3, 4}
        and count("LWPOLYLINE") in {2, 3}
        and 3.0 <= aspect_ratio <= 4.2
        and 0.45 <= normalized_arc_radius <= 0.6
    ):
        return (
            "non_electrical.equipment_graphic.v1",
            "confirmed-tall-equipment-graphic-geometry-v1",
            0.95,
        )
    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and 1 <= count("LINE") <= 3
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.4 <= aspect_ratio <= 1.9
    ):
        return (
            "non_electrical.placeholder.v1",
            "confirmed-placeholder-geometry-v1",
            0.93,
        )
    if (
        port_count == 2
        and len(arc_radii) == 4
        and count("LWPOLYLINE") == 2
        and count("LINE") == 0
        and aspect_ratio >= 8.0
    ):
        return (
            "line_break.non_connective.v1",
            "confirmed-line-break-geometry-v1",
            0.98,
        )
    return None


def _has_wide_ge_gx_switch_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a complete wide GE/GX equipment face, invariant to scale/rotation."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping):
        return False

    def count(name: str) -> int:
        try:
            return int(histogram.get(name, 0))
        except (TypeError, ValueError):
            return 0

    try:
        aspect = float(shape.get("oriented_aspect_ratio") or 0.0)
        bulged_count = int(shape.get("closed_bulged_lwpolyline_count", 0))
    except (TypeError, ValueError):
        return False
    if not (
        port_count == 2
        and 20 <= count("ARC") <= 28
        and count("CIRCLE") == 8
        and 45 <= count("HATCH") <= 65
        and 1 <= count("INSERT") <= 5
        and 75 <= count("LINE") <= 105
        and 120 <= count("LWPOLYLINE") <= 155
        and 70 <= count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF") <= 90
        and 3.8 <= aspect <= 4.6
        and bulged_count >= 40
    ):
        return False

    values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    required_labels = (
        {f"P{index}" for index in range(1, 25)}
        | {f"GE{index}" for index in range(1, 25)}
        | {f"GX{index}" for index in range(25, 29)}
        | {f"{index}{suffix}" for index in range(1, 5) for suffix in ("T", "R")}
        | {"CONSOLE", "FAULT", "PWR", "PWR1", "PWR2", "+/L", "-/N"}
    )
    if not required_labels <= values:
        return False

    panel = shape.get("communication_panel_features")
    if not isinstance(panel, Mapping):
        return False
    try:
        square_count = int(panel.get("square_cell_count", 0))
        cell_aspect = float(panel.get("dominant_cell_aspect", 0.0))
    except (TypeError, ValueError):
        return False
    if square_count < 24 or not 0.9 <= cell_aspect <= 1.12:
        return False

    parsed: list[tuple[float, float, float]] = []
    for item in shape.get("normalized_circles") or []:
        if not isinstance(item, Mapping):
            return False
        center = item.get("center")
        try:
            if not isinstance(center, Sequence) or len(center) < 2:
                return False
            parsed.append((float(center[0]), float(center[1]), float(item["radius"])))
        except (KeyError, TypeError, ValueError):
            return False
    if len(parsed) != 8:
        return False
    radii = [item[2] for item in parsed]
    mean_radius = sum(radii) / len(radii)
    if mean_radius <= 1e-9 or max(radii) / min(radii) > 1.03:
        return False

    # Derive the circle-row axis from the farthest pair, so a rotated block
    # retains the same ordered spacing signature.
    start, end = max(
        ((left, right) for i, left in enumerate(parsed) for right in parsed[i + 1 :]),
        key=lambda pair: math.hypot(pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]),
    )
    axis_x, axis_y = end[0] - start[0], end[1] - start[1]
    axis_length = math.hypot(axis_x, axis_y)
    if axis_length <= 1e-9:
        return False
    unit_x, unit_y = axis_x / axis_length, axis_y / axis_length
    normal_x, normal_y = -unit_y, unit_x
    projected = sorted(
        (
            (x - start[0]) * unit_x + (y - start[1]) * unit_y,
            abs((x - start[0]) * normal_x + (y - start[1]) * normal_y),
        )
        for x, y, _ in parsed
    )
    if max(offset for _, offset in projected) > mean_radius * 0.08:
        return False
    gaps = [
        (projected[index + 1][0] - projected[index][0]) / mean_radius
        for index in range(7)
    ]
    return all(
        3.15 <= gap <= 3.60 if index % 2 == 0 else 4.55 <= gap <= 5.10
        for index, gap in enumerate(gaps)
    )


def _principal_circle_rows(
    shape: Mapping[str, Any], *, row_counts: Sequence[int]
) -> tuple[list[list[float]], float] | None:
    """Return principal-axis projections for strict equal-radius circle rows."""
    try:
        circles = shape.get("normalized_circles") or []
        parsed = [
            (float(item["center"][0]), float(item["center"][1]), float(item["radius"]))
            for item in circles
        ]
        if len(parsed) != sum(row_counts):
            return None
        radii = [item[2] for item in parsed]
        radius = sum(radii) / len(radii)
        if radius <= 1e-9 or max(radii) / min(radii) > 1.03:
            return None
        cx = sum(item[0] for item in parsed) / len(parsed)
        cy = sum(item[1] for item in parsed) / len(parsed)
        xx = sum((item[0] - cx) ** 2 for item in parsed)
        yy = sum((item[1] - cy) ** 2 for item in parsed)
        xy = sum((item[0] - cx) * (item[1] - cy) for item in parsed)
        angle = .5 * math.atan2(2.0 * xy, xx - yy)
        axis = (math.cos(angle), math.sin(angle))
        normal = (-axis[1], axis[0])
        values = sorted(
            (
                (item[0] - cx) * normal[0] + (item[1] - cy) * normal[1],
                (item[0] - cx) * axis[0] + (item[1] - cy) * axis[1],
            )
            for item in parsed
        )
        groups: list[list[tuple[float, float]]] = []
        for normal_value, axial_value in values:
            if not groups or abs(normal_value - sum(item[0] for item in groups[-1]) / len(groups[-1])) > radius * .25:
                groups.append([(normal_value, axial_value)])
            else:
                groups[-1].append((normal_value, axial_value))
        if sorted(len(group) for group in groups) != sorted(row_counts):
            return None
        if any(max(item[0] for item in group) - min(item[0] for item in group) > radius * .12 for group in groups):
            return None
        return [sorted(item[1] for item in group) for group in groups], radius
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def _has_dgicom_8g12_equipment_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Strict complete-parent model for the 40-circle DGICOM 8G12 face."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    labels = {str(value or "").strip().upper() for value in shape.get("text_values") or [] if str(value or "").strip()}
    required = (
        {f"GX{index}" for index in range(9, 29)}
        | {f"GE{index}" for index in range(1, 17)}
        | {f"P{index}" for index in range(1, 17)}
        | {f"{index}{suffix}" for index in range(1, 21) for suffix in ("T", "R")}
        | {"COMBO", "CONSOLE", "PWR", "PWR1", "PWR2", "FAULT", "+/L", "-/N"}
    )
    panel = shape.get("communication_panel_features")
    if not (
        port_count == 2
        and {key: int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "HATCH", "INSERT", "LINE", "LWPOLYLINE", "TEXT")}
        == {"ARC": 120, "CIRCLE": 40, "HATCH": 54, "INSERT": 3, "LINE": 379, "LWPOLYLINE": 252, "TEXT": 111}
        and required <= labels
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 65
        and int(shape.get("parallel_line_group_max", 0)) >= 200
        and 3.9 <= float(shape.get("oriented_aspect_ratio") or 0.0) <= 4.1
        and isinstance(panel, Mapping)
        and int(panel.get("square_cell_count", 0)) == 17
        and 1.0 <= float(panel.get("dominant_cell_aspect", 0.0)) <= 1.07
    ):
        return False
    rows = _principal_circle_rows(shape, row_counts=(20, 20))
    if rows is None:
        return False
    projections, radius = rows
    signatures = []
    for row in projections:
        gaps = sorted(round((right - left) / radius, 2) for left, right in zip(row, row[1:]))
        signatures.append(gaps)
        if not (
            len(gaps) == 19
            and sum(3.20 <= gap <= 3.50 for gap in gaps) == 10
            and sum(3.55 <= gap <= 3.80 for gap in gaps) == 1
            and sum(4.70 <= gap <= 5.00 for gap in gaps) == 6
            and sum(7.00 <= gap <= 7.35 for gap in gaps) == 2
        ):
            return False
    return all(abs(left - right) <= .08 for left, right in zip(signatures[0], signatures[1]))


def _has_wyd_communication_equipment_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Strict complete-parent model for the 8-COM/12-LAN WYD face."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    labels = {str(value or "").strip().upper() for value in shape.get("text_values") or [] if str(value or "").strip()}
    required = (
        {f"COM{index}" for index in range(1, 9)}
        | {f"LAN{index}" for index in range(1, 13)}
        | {"USB", "VGA", "B+", "B-", "PWR1", "PWR2", "+/L", "-/N", "DO1", "DO2"}
    )
    panel = shape.get("communication_panel_features")
    if not (
        port_count == 2
        and {key: int(h.get(key, 0)) for key in ("ARC", "CIRCLE", "HATCH", "INSERT", "LINE", "LWPOLYLINE", "TEXT")}
        == {"ARC": 4, "CIRCLE": 15, "HATCH": 24, "INSERT": 5, "LINE": 17, "LWPOLYLINE": 189, "TEXT": 96}
        and required <= labels
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 74
        and 2.95 <= float(shape.get("oriented_aspect_ratio") or 0.0) <= 3.15
        and isinstance(panel, Mapping)
        and int(panel.get("square_cell_count", 0)) == 56
        and int(panel.get("labelled_cell_count", 0)) == 50
        and int(panel.get("lan_socket_port_count", 0)) == 12
        and int(panel.get("group_counts", {}).get("COM", 0)) == 8
        and int(panel.get("group_counts", {}).get("LAN", 0)) == 12
        and .97 <= float(panel.get("dominant_cell_aspect", 0.0)) <= 1.03
    ):
        return False
    rows = _principal_circle_rows(shape, row_counts=(5, 5, 5))
    if rows is None:
        return False
    projections, radius = rows
    for row in projections:
        gaps = [(right - left) / radius for left, right in zip(row, row[1:])]
        if len(gaps) != 4 or any(not 7.75 <= gap <= 8.20 for gap in gaps):
            return False
    centers = [sum(row) / len(row) for row in projections]
    centers.sort()
    offsets = [(centers[index + 1] - centers[index]) / radius for index in range(2)]
    return 0.0 <= offsets[0] <= .15 and 3.75 <= offsets[1] <= 4.25


def _has_two_contact_mechanical_actuator_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the PWF176-style two-contact mechanism without its name.

    The two round contacts are the only external ports.  The open blade and
    lower mechanical actuator are body geometry and never grant conductivity.
    All comparisons are contact-radius normalized and therefore invariant to
    definition rotation and uniform scale.
    """

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    try:
        if not (
            port_count == 2
            and int(histogram.get("LINE", 0)) == 9
            and int(histogram.get("LWPOLYLINE", 0)) == 2
            and sum(int(value) for value in histogram.values()) == 11
            and len(contacts) == 2
            and len(segments) == 9
        ):
            return False
        parsed_contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in contacts
        ]
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False

    radii = [radius for _, radius in parsed_contacts]
    radius = sum(radii) / 2.0
    if radius <= 1e-9 or max(radii) / min(radii) > 1.03:
        return False
    first, second = (item[0] for item in parsed_contacts)
    axis = (second[0] - first[0], second[1] - first[1])
    contact_spacing = math.hypot(axis[0], axis[1])
    if not 22.2 <= contact_spacing / radius <= 22.8:
        return False
    unit = (axis[0] / contact_spacing, axis[1] / contact_spacing)
    normal = (-unit[1], unit[0])
    midpoint = ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)

    def coordinates(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - midpoint[0], point[1] - midpoint[1]
        return (
            (dx * unit[0] + dy * unit[1]) / radius,
            (dx * normal[0] + dy * normal[1]) / radius,
        )

    rows = []
    for start, end in parsed_segments:
        local_start, local_end = coordinates(start), coordinates(end)
        dx, dy = local_end[0] - local_start[0], local_end[1] - local_start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        rows.append(
            {
                "start": local_start,
                "end": local_end,
                "length": length,
                "axis_alignment": abs(dx) / length,
                "normal_alignment": abs(dy) / length,
            }
        )

    contact_axis = contact_spacing / radius / 2.0
    leads = []
    for row in rows:
        endpoints = (row["start"], row["end"])
        if (
            row["axis_alignment"] >= 0.995
            and max(abs(point[1]) for point in endpoints) <= 0.08
            and 7.3 <= row["length"] <= 7.7
            and any(abs(abs(point[0]) - contact_axis) <= 0.08 for point in endpoints)
        ):
            leads.append(row)
    if len(leads) != 2:
        return False
    lead_sides = {
        1 if max(row["start"][0], row["end"][0]) > contact_axis - 0.08 else -1
        for row in leads
    }
    if lead_sides != {-1, 1}:
        return False

    remaining = [row for row in rows if row not in leads]
    oblique = [
        row
        for row in remaining
        if 8.2 <= row["length"] <= 8.6
        and 0.86 <= row["axis_alignment"] <= 0.93
        and any(abs(point[1]) <= 0.08 and 3.6 <= abs(point[0]) <= 3.9 for point in (row["start"], row["end"]))
    ]
    if len(oblique) != 1:
        return False
    actuator = [row for row in remaining if row is not oblique[0]]
    axis_bars = [row for row in actuator if row["axis_alignment"] >= 0.995]
    normal_bars = [row for row in actuator if row["normal_alignment"] >= 0.995]
    if len(axis_bars) != 1 or len(normal_bars) != 5:
        return False
    bottom = axis_bars[0]
    if not (
        3.65 <= bottom["length"] <= 3.85
        and abs((bottom["start"][0] + bottom["end"][0]) / 2.0) <= 0.08
        and 8.9 <= abs((bottom["start"][1] + bottom["end"][1]) / 2.0) <= 9.2
    ):
        return False
    if any(not 1.4 <= row["length"] <= 1.75 for row in normal_bars):
        return False
    axial_offsets = sorted(
        abs((row["start"][0] + row["end"][0]) / 2.0) for row in normal_bars
    )
    if not (
        all(value <= 0.08 for value in axial_offsets[:3])
        and all(1.75 <= value <= 2.0 for value in axial_offsets[3:])
    ):
        return False
    normal_offsets = sorted(
        abs((row["start"][1] + row["end"][1]) / 2.0) for row in normal_bars
    )
    return bool(
        2.55 <= normal_offsets[0] <= 2.85
        and 5.3 <= normal_offsets[1] <= 5.65
        and all(8.05 <= value <= 8.5 for value in normal_offsets[2:])
    )


def _has_dgicom3000_4gx8ge_hv_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the complete 4GX/8GE DGICOM3000-4GX8GE-HV face.

    The fingerprint is deliberately absent here: it is provenance only.  The
    complete census, labels, square-cell count and affine-invariant optical
    array must all agree before the whole block is ignored.
    """
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping) or port_count != 2:
        return False
    def count(name: str) -> int:
        try:
            return int(histogram.get(name, 0))
        except (TypeError, ValueError):
            return -1
    if {name: count(name) for name in ("ARC", "CIRCLE", "LINE", "LWPOLYLINE")} != {
        "ARC": 24, "CIRCLE": 8, "LINE": 96, "LWPOLYLINE": 70
    } or count("HATCH") != 20 or count("INSERT") != 1 or count("TEXT") != 38:
        return False
    if abs(float(shape.get("oriented_aspect_ratio") or 0) - 2.117647) > 0.015:
        return False
    values = {str(v or "").strip().upper() for v in shape.get("text_values") or []}
    required = ({f"GE{i}" for i in range(1, 9)} | {f"GX{i}" for i in range(9, 13)} |
                {f"{row}{side}" for row in range(1, 5) for side in ("GT", "GR")} |
                {"CONSOLE", "+/L", "-/N"} | {str(i) for i in range(1, 7)})
    if not required <= values:
        return False
    panel = shape.get("communication_panel_features") or {}
    try:
        if int(panel.get("square_cell_count", 0)) != 9 or int(shape.get("parallel_line_group_max", 0)) != 49:
            return False
    except (TypeError, ValueError):
        return False
    circles = shape.get("normalized_circles") or []
    try:
        centers = [(float(c["center"][0]), float(c["center"][1])) for c in circles]
        radii = [float(c["radius"]) for c in circles]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(centers) != 8 or min(radii, default=0) <= 0 or max(radii) / min(radii) > 1.03:
        return False
    distances = sorted(math.hypot(x2-x1, y2-y1) for i, (x1, y1) in enumerate(centers)
                       for x2, y2 in centers[i+1:])
    base = distances[0]
    expected = [1.0, 1.0, 1.0, 1.0, 1.44, 1.44, 2.44, 2.44, 2.44, 2.44,
                2.788, 2.788, 2.788, 2.788, 2.952, 2.952, 2.973, 2.973,
                3.124, 3.152, 3.44, 3.44, 3.685, 3.685, 3.726, 3.726,
                4.404, 4.452]
    return all(abs(value / base - target) <= 0.08 for value, target in zip(distances, expected))


def _has_compact_ge_gx_switch_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a compact 8-GE/2-GX equipment face without using its name."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping):
        return False

    def count(name: str) -> int:
        try:
            return int(histogram.get(name, 0))
        except (TypeError, ValueError):
            return 0

    try:
        aspect = float(shape.get("oriented_aspect_ratio") or 0.0)
        bulged_count = int(shape.get("closed_bulged_lwpolyline_count", 0))
    except (TypeError, ValueError):
        return False
    if not (
        port_count == 2
        and 10 <= count("ARC") <= 14
        and count("CIRCLE") == 4
        and 16 <= count("HATCH") <= 22
        and 1 <= count("INSERT") <= 3
        and 50 <= count("LINE") <= 70
        and 45 <= count("LWPOLYLINE") <= 60
        and 28
        <= count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF")
        <= 38
        and 1.7 <= aspect <= 2.1
        and 15 <= bulged_count <= 22
        and int(shape.get("parallel_line_group_max", 0)) >= 24
    ):
        return False

    values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    required_labels = (
        {f"GE{index}" for index in range(1, 9)}
        | {"GX9", "GX10", "1GT", "1GR", "2GT", "2GR"}
        | {"CONSOLE", "+/L", "-/N"}
    )
    if not required_labels <= values:
        return False

    panel = shape.get("communication_panel_features")
    if not isinstance(panel, Mapping):
        return False
    try:
        square_count = int(panel.get("square_cell_count", 0))
        cell_aspect = float(panel.get("dominant_cell_aspect", 0.0))
    except (TypeError, ValueError):
        return False
    if not (8 <= square_count <= 10 and 0.90 <= cell_aspect <= 1.05):
        return False

    circles = shape.get("normalized_circles") or []
    try:
        radii = [float(item["radius"]) for item in circles]
    except (KeyError, TypeError, ValueError):
        return False
    if not (
        len(circles) == 4
        and min(radii, default=0.0) > 1e-9
        and max(radii) / min(radii) <= 1.03
    ):
        return False
    mean_radius = sum(radii) / 4.0
    try:
        centers = [
            (float(item["center"][0]), float(item["center"][1]))
            for item in circles
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    pair_distances = sorted(
        math.hypot(right[0] - left[0], right[1] - left[1]) / mean_radius
        for index, left in enumerate(centers)
        for right in centers[index + 1 :]
    )
    return bool(
        len(pair_distances) == 6
        and all(3.2 <= value <= 3.5 for value in pair_distances[:2])
        and all(9.2 <= value <= 9.6 for value in pair_distances[2:4])
        and all(9.75 <= value <= 10.2 for value in pair_distances[4:])
    )


def _has_hykl_dual_row_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize an enclosed 4x2 PE/GND/TX/RX interface face."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping):
        return False

    def count(name: str) -> int:
        try:
            return int(histogram.get(name, 0))
        except (TypeError, ValueError):
            return 0

    if not (
        port_count == 2
        and count("CIRCLE") == 8
        and count("LWPOLYLINE") == 9
        and count("TEXT") == 16
        and count("MTEXT") == 1
        and count("LINE") + count("ARC") + count("HATCH") + count("INSERT") == 0
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 9
    ):
        return False
    values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    if not {"PE1", "PE2", "GND", "TX", "RX", "IN", "OUT"} <= values:
        return False

    try:
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(circles) != 8 or len(contacts) != 9:
        return False
    circle_radii = [radius for _, radius in circles]
    if min(circle_radii) <= 1e-9 or max(circle_radii) / min(circle_radii) > 1.03:
        return False
    circle_radius = sum(circle_radii) / 8.0
    contacts = sorted(contacts, key=lambda item: item[1])
    small_contacts, panel_body = contacts[:8], contacts[8]
    small_radii = [radius for _, radius in small_contacts]
    if (
        min(small_radii) <= 1e-9
        or max(small_radii) / min(small_radii) > 1.03
        or panel_body[1] / (sum(small_radii) / 8.0) < 60.0
    ):
        return False

    closest = min(
        (
            (math.hypot(right[0][0] - left[0][0], right[0][1] - left[0][1]), left[0], right[0])
            for index, left in enumerate(circles)
            for right in circles[index + 1 :]
        ),
        key=lambda item: item[0],
    )
    if closest[0] <= 1e-9:
        return False
    axis_x = (closest[2][0] - closest[1][0]) / closest[0]
    axis_y = (closest[2][1] - closest[1][1]) / closest[0]
    normal_x, normal_y = -axis_y, axis_x
    center = (
        sum(point[0] for point, _ in circles) / 8.0,
        sum(point[1] for point, _ in circles) / 8.0,
    )

    def clusters(values: list[float], tolerance: float) -> list[list[float]]:
        grouped: list[list[float]] = []
        for value in sorted(values):
            if not grouped or abs(value - sum(grouped[-1]) / len(grouped[-1])) > tolerance:
                grouped.append([value])
            else:
                grouped[-1].append(value)
        return grouped

    axis_values = [
        (point[0] - center[0]) * axis_x + (point[1] - center[1]) * axis_y
        for point, _ in circles
    ]
    normal_values = [
        (point[0] - center[0]) * normal_x + (point[1] - center[1]) * normal_y
        for point, _ in circles
    ]
    axis_groups = clusters(axis_values, circle_radius * 0.15)
    normal_groups = clusters(normal_values, circle_radius * 0.15)
    if not (
        len(axis_groups) == 4
        and all(len(group) == 2 for group in axis_groups)
        and len(normal_groups) == 2
        and all(len(group) == 4 for group in normal_groups)
    ):
        return False
    axis_centers = [sum(group) / len(group) for group in axis_groups]
    normal_centers = [sum(group) / len(group) for group in normal_groups]
    axis_gaps = [
        (axis_centers[index + 1] - axis_centers[index]) / circle_radius
        for index in range(3)
    ]
    normal_gap = (normal_centers[1] - normal_centers[0]) / circle_radius
    if not (
        all(3.95 <= gap <= 4.2 for gap in axis_gaps)
        and 8.0 <= normal_gap <= 8.3
    ):
        return False

    used_circles: set[int] = set()
    for contact_center, _ in small_contacts:
        nearest_distance, circle_index = min(
            (
                math.hypot(
                    contact_center[0] - circle_center[0],
                    contact_center[1] - circle_center[1],
                ),
                index,
            )
            for index, (circle_center, _) in enumerate(circles)
        )
        if (
            not 0.95 <= nearest_distance / circle_radius <= 1.08
            or circle_index in used_circles
        ):
            return False
        used_circles.add(circle_index)
    return len(used_circles) == 8


def _has_firewall_eth_panel_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a dense ETH firewall face with USB and optical circle arrays."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    if not isinstance(histogram, Mapping):
        return False

    def count(name: str) -> int:
        try:
            return int(histogram.get(name, 0))
        except (TypeError, ValueError):
            return 0

    try:
        aspect = float(shape.get("oriented_aspect_ratio") or 0.0)
        bulged_count = int(shape.get("closed_bulged_lwpolyline_count", 0))
        parallel_max = int(shape.get("parallel_line_group_max", 0))
    except (TypeError, ValueError):
        return False
    if not (
        port_count == 2
        and 20 <= count("ARC") <= 28
        and count("CIRCLE") == 12
        and 24 <= count("HATCH") <= 34
        and 80 <= count("LINE") <= 100
        and 108 <= count("LWPOLYLINE") <= 132
        and 42
        <= count("TEXT") + count("MTEXT") + count("ATTRIB") + count("ATTDEF")
        <= 52
        and 3.6 <= aspect <= 4.2
        and 24 <= bulged_count <= 34
        and parallel_max >= 45
    ):
        return False
    values = {
        str(value or "").strip().upper()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    required_labels = (
        {f"ETH{index}" for index in range(0, 11)}
        | {"ETH12", "ETH13"}
        | {f"P{index}" for index in range(1, 13)}
        | {f"{index}{suffix}" for index in range(1, 5) for suffix in ("T", "R")}
        | {"USB", "CONSOLE", "L1", "N1", "PE1", "J1", "L2", "N2", "PE2", "J2"}
    )
    if not required_labels <= values:
        return False
    panel = shape.get("communication_panel_features")
    if not isinstance(panel, Mapping):
        return False
    try:
        square_count = int(panel.get("square_cell_count", 0))
        cell_aspect = float(panel.get("dominant_cell_aspect", 0.0))
    except (TypeError, ValueError):
        return False
    if not (12 <= square_count <= 14 and 0.95 <= cell_aspect <= 1.08):
        return False

    try:
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(circles) != 12:
        return False
    circles = sorted(circles, key=lambda item: item[1])
    small, large = circles[:4], circles[4:]
    small_radius = sum(radius for _, radius in small) / 4.0
    large_radius = sum(radius for _, radius in large) / 8.0
    if not (
        small_radius > 1e-9
        and max(radius for _, radius in small) / min(radius for _, radius in small) <= 1.03
        and max(radius for _, radius in large) / min(radius for _, radius in large) <= 1.03
        and 1.62 <= large_radius / small_radius <= 1.75
    ):
        return False

    small_start, small_end = max(
        (
            (left[0], right[0])
            for index, left in enumerate(small)
            for right in small[index + 1 :]
        ),
        key=lambda pair: math.hypot(
            pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]
        ),
    )
    dx, dy = small_end[0] - small_start[0], small_end[1] - small_start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return False
    axis_x, axis_y = dx / length, dy / length
    normal_x, normal_y = -axis_y, axis_x
    projected_small = sorted(
        (
            (point[0] - small_start[0]) * axis_x + (point[1] - small_start[1]) * axis_y,
            abs((point[0] - small_start[0]) * normal_x + (point[1] - small_start[1]) * normal_y),
        )
        for point, _ in small
    )
    if max(offset for _, offset in projected_small) > small_radius * 0.08:
        return False
    small_gaps = [
        (projected_small[index + 1][0] - projected_small[index][0]) / small_radius
        for index in range(3)
    ]
    if not all(3.1 <= gap <= 3.3 for gap in small_gaps):
        return False

    closest = min(
        (
            (math.hypot(right[0][0] - left[0][0], right[0][1] - left[0][1]), left[0], right[0])
            for index, left in enumerate(large)
            for right in large[index + 1 :]
        ),
        key=lambda item: item[0],
    )
    if closest[0] <= 1e-9:
        return False
    axis_x = (closest[2][0] - closest[1][0]) / closest[0]
    axis_y = (closest[2][1] - closest[1][1]) / closest[0]
    normal_x, normal_y = -axis_y, axis_x
    center = (
        sum(point[0] for point, _ in large) / 8.0,
        sum(point[1] for point, _ in large) / 8.0,
    )

    def clusters(values: list[float], tolerance: float) -> list[list[float]]:
        grouped: list[list[float]] = []
        for value in sorted(values):
            if not grouped or abs(value - sum(grouped[-1]) / len(grouped[-1])) > tolerance:
                grouped.append([value])
            else:
                grouped[-1].append(value)
        return grouped

    axis_groups = clusters(
        [
            (point[0] - center[0]) * axis_x + (point[1] - center[1]) * axis_y
            for point, _ in large
        ],
        large_radius * 0.15,
    )
    normal_groups = clusters(
        [
            (point[0] - center[0]) * normal_x + (point[1] - center[1]) * normal_y
            for point, _ in large
        ],
        large_radius * 0.15,
    )
    if not (
        len(axis_groups) == 4
        and all(len(group) == 2 for group in axis_groups)
        and len(normal_groups) == 2
        and all(len(group) == 4 for group in normal_groups)
    ):
        return False
    axis_centers = [sum(group) / len(group) for group in axis_groups]
    normal_centers = [sum(group) / len(group) for group in normal_groups]
    axis_gaps = [
        (axis_centers[index + 1] - axis_centers[index]) / large_radius
        for index in range(3)
    ]
    normal_gap = (normal_centers[1] - normal_centers[0]) / large_radius
    return bool(
        3.2 <= axis_gaps[0] <= 3.5
        and 5.7 <= axis_gaps[1] <= 6.1
        and 3.2 <= axis_gaps[2] <= 3.5
        and 14.8 <= normal_gap <= 15.4
    )


def _is_communication_multiport_panel_geometry(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    panel = shape.get("communication_panel_features")
    if not isinstance(panel, Mapping):
        return False
    groups = panel.get("group_counts")
    if not isinstance(groups, Mapping):
        return False
    try:
        square_count = int(panel.get("square_cell_count", 0))
        labelled_count = int(panel.get("labelled_cell_count", 0))
        mapped_cell_count = int(panel.get("mapped_cell_port_count", 0))
        lan_socket_count = int(panel.get("lan_socket_port_count", 0))
        row_count = int(panel.get("row_count", 0))
        com_count = int(groups.get("COM", 0))
        can_count = int(groups.get("CAN", 0))
        lan_count = int(groups.get("LAN", 0))
        cell_aspect = float(panel.get("dominant_cell_aspect", 0.0))
    except (TypeError, ValueError):
        return False
    return (
        port_count >= 20
        and mapped_cell_count >= 20
        and square_count >= mapped_cell_count
        and labelled_count >= mapped_cell_count
        and port_count == mapped_cell_count + lan_socket_count
        and row_count == 2
        and com_count >= 4
        and can_count >= 1
        and lan_count >= 1
        and 0.9 <= cell_aspect <= 1.1
    )


def _has_ethernet_lan_port_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the PWF330 LAN socket by text and contact/body topology."""
    values = {str(value).strip().upper() for value in (
        shape.get("text_values") or shape.get("normalized_text_values") or []
    )}
    if values != {"ETHER", "NET"}:
        return False
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if int(histogram.get("LWPOLYLINE", 0)) != 3:
            return False
        if int(histogram.get("LINE", 0)) != 0 or int(histogram.get("TEXT", 0)) != 2:
            return False
    except (TypeError, ValueError):
        return False
    bodies = shape.get("normalized_closed_straight_lwpolylines") or shape.get(
        "normalized_closed_straight_polylines"
    ) or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if len(bodies) != 1 or len(contacts) != 2:
        return False
    try:
        body = bodies[0]
        edge_lengths = sorted(float(value) for value in body.get("edge_lengths", []))
        if len(edge_lengths) != 4 or edge_lengths[0] <= 1e-9:
            return False
        if edge_lengths[-1] / edge_lengths[0] > 1.05:
            return False
        body_center = (
            float(body["center"][0]),
            float(body["center"][1]),
        )
        contact_centers = [
            (float(item["center"][0]), float(item["center"][1]))
            for item in contacts
        ]
        contact_radii = sorted(float(item["radius"]) for item in contacts)
        if contact_radii[0] <= 1e-9 or contact_radii[1] / contact_radii[0] > 1.1:
            return False
        axis_x = contact_centers[1][0] - contact_centers[0][0]
        axis_y = contact_centers[1][1] - contact_centers[0][1]
        contact_spacing = math.hypot(axis_x, axis_y)
        body_side = sum(edge_lengths) / len(edge_lengths)
        if not (1.25 * body_side <= contact_spacing <= 1.75 * body_side):
            return False
        axis_x, axis_y = axis_x / contact_spacing, axis_y / contact_spacing
        body_dx = body_center[0] - contact_centers[0][0]
        body_dy = body_center[1] - contact_centers[0][1]
        projection = (body_dx * axis_x + body_dy * axis_y) / contact_spacing
        perpendicular = abs(body_dx * axis_y - body_dy * axis_x)
        return 0.2 <= projection <= 0.8 and perpendicular <= 0.05 * body_side
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return False


def _has_three_lead_box_topology(shape: Mapping[str, Any]) -> bool:
    """Bind two nested rectangles, three outward leads, and one diagonal."""

    bodies = shape.get("normalized_closed_straight_lwpolylines") or []
    segments = shape.get("normalized_line_segments") or []
    if len(bodies) != 2 or len(segments) != 4:
        return False
    try:
        parsed_bodies = []
        for body in bodies:
            center = (float(body["center"][0]), float(body["center"][1]))
            lengths = sorted(float(value) for value in body["edge_lengths"])
            if (
                len(lengths) != 4
                or lengths[0] <= 1e-9
                or abs(lengths[1] - lengths[0]) > lengths[0] * 0.04
                or abs(lengths[3] - lengths[2]) > lengths[2] * 0.04
            ):
                return False
            parsed_bodies.append((center, lengths[0], lengths[2]))
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False

    big = max(parsed_bodies, key=lambda item: item[2])
    small = min(parsed_bodies, key=lambda item: item[2])
    big_center, shared_width, big_height = big
    small_center, small_height, small_width = small
    if not (
        2.45 <= big_height / shared_width <= 2.55
        and 0.97 <= small_width / shared_width <= 1.03
        and 0.47 <= small_height / shared_width <= 0.53
        and 0.97
        <= math.hypot(
            small_center[0] - big_center[0], small_center[1] - big_center[1]
        )
        / shared_width
        <= 1.03
    ):
        return False

    def vector(
        segment: tuple[tuple[float, float], tuple[float, float]]
    ) -> tuple[float, float, float]:
        dx = segment[1][0] - segment[0][0]
        dy = segment[1][1] - segment[0][1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError("degenerate segment")
        return dx / length, dy / length, length

    try:
        vectors = [vector(segment) for segment in parsed_segments]
    except ValueError:
        return False
    lead_indices = [
        index
        for index, (_, _, length) in enumerate(vectors)
        if 0.97 <= length / shared_width <= 1.03
    ]
    if len(lead_indices) != 3:
        return False
    diagonal_indices = [index for index in range(4) if index not in lead_indices]
    if len(diagonal_indices) != 1:
        return False
    diagonal = parsed_segments[diagonal_indices[0]]
    diagonal_length = vectors[diagonal_indices[0]][2]
    if not (1.09 <= diagonal_length / shared_width <= 1.15):
        return False

    reference_x, reference_y, _ = vectors[lead_indices[0]]
    if any(
        abs(reference_x * vectors[index][1] - reference_y * vectors[index][0])
        > 0.04
        for index in lead_indices[1:]
    ):
        return False
    center_dx = small_center[0] - big_center[0]
    center_dy = small_center[1] - big_center[1]
    if abs(center_dx * reference_x + center_dy * reference_y) > shared_width * 0.04:
        return False
    normal_x, normal_y = -reference_y, reference_x

    def project(point: tuple[float, float], center: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - center[0], point[1] - center[1]
        return dx * reference_x + dy * reference_y, dx * normal_x + dy * normal_y

    diagonal_offsets = [project(point, small_center) for point in diagonal]
    if any(
        abs(abs(axis) - shared_width * 0.5) > shared_width * 0.04
        or abs(abs(normal) - shared_width * 0.25) > shared_width * 0.04
        for axis, normal in diagonal_offsets
    ):
        return False
    if (
        abs(diagonal_offsets[0][0] + diagonal_offsets[1][0]) > shared_width * 0.04
        or abs(diagonal_offsets[0][1] + diagonal_offsets[1][1]) > shared_width * 0.04
    ):
        return False

    side_signs: list[int] = []
    attachment_levels: list[float] = []
    for index in lead_indices:
        offsets = [project(point, big_center) for point in parsed_segments[index]]
        attached = [
            endpoint
            for endpoint, (axis, normal) in enumerate(offsets)
            if abs(abs(axis) - shared_width * 0.5) <= shared_width * 0.04
            and abs(normal) <= big_height * 0.5 + shared_width * 0.04
        ]
        if len(attached) != 1:
            return False
        attached_axis, attached_normal = offsets[attached[0]]
        outer_axis, outer_normal = offsets[1 - attached[0]]
        sign = 1 if attached_axis > 0.0 else -1
        if not (
            outer_axis * sign > 0.0
            and abs(abs(outer_axis) - shared_width * 1.5) <= shared_width * 0.05
            and abs(outer_normal - attached_normal) <= shared_width * 0.04
        ):
            return False
        side_signs.append(sign)
        attachment_levels.append(attached_normal)
    if sorted(side_signs) not in ([-1, -1, 1], [-1, 1, 1]):
        return False
    return all(
        abs(left - right) >= shared_width * 0.1
        for left, right in zip(
            sorted(attachment_levels), sorted(attachment_levels)[1:]
        )
    )


def _has_named_four_contact_two_port_strip_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize the AK-style four-contact/two-circle external strip."""

    if port_count != 2:
        return False
    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if not (
            int(histogram.get("LINE", 0)) == 7
            and int(histogram.get("LWPOLYLINE", 0)) == 4
            and int(histogram.get("CIRCLE", 0)) == 2
            and int(histogram.get("TEXT", 0)) == 0
        ):
            return False
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item.get("radius"))),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(contacts) != 4 or len(circles) != 2 or len(segments) != 7:
        return False
    contact_radius = sum(radius for _, radius in contacts) / 4.0
    if contact_radius <= 1e-9 or any(
        abs(radius - contact_radius) > contact_radius * 0.05
        for _, radius in contacts
    ):
        return False

    farthest = max(
        (
            (left, right, math.hypot(
                contacts[right][0][0] - contacts[left][0][0],
                contacts[right][0][1] - contacts[left][0][1],
            ))
            for left in range(4)
            for right in range(left + 1, 4)
        ),
        key=lambda item: item[2],
    )
    if farthest[2] <= 1e-9:
        return False
    origin = contacts[farthest[0]][0]
    axis_x = (contacts[farthest[1]][0][0] - origin[0]) / farthest[2]
    axis_y = (contacts[farthest[1]][0][1] - origin[1]) / farthest[2]
    normal_x, normal_y = -axis_y, axis_x

    def project(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        return dx * axis_x + dy * axis_y, dx * normal_x + dy * normal_y

    ordered_contacts = sorted(
        ((project(center)[0], project(center)[1], center) for center, _ in contacts),
        key=lambda item: item[0],
    )
    if any(abs(item[1]) > contact_radius * 0.08 for item in ordered_contacts):
        return False
    gaps = [
        (ordered_contacts[index + 1][0] - ordered_contacts[index][0])
        / contact_radius
        for index in range(3)
    ]
    if not (
        4.9 <= gaps[0] <= 5.1
        and 29.5 <= gaps[1] <= 30.5
        and 4.9 <= gaps[2] <= 5.1
    ):
        return False
    for circle_center, circle_radius in circles:
        if not (2.9 <= circle_radius / contact_radius <= 3.1):
            return False
        if min(
            math.hypot(circle_center[0] - item[2][0], circle_center[1] - item[2][1])
            for item in ordered_contacts[1:3]
        ) > contact_radius * 0.08:
            return False
    if any(
        min(
            math.hypot(circle_center[0] - item[2][0], circle_center[1] - item[2][1])
            for circle_center, _ in circles
        )
        > contact_radius * 0.08
        for item in ordered_contacts[1:3]
    ):
        return False

    vectors = []
    for start, end in segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        vectors.append((dx / length, dy / length, length, start, end))
    axial = [
        item for item in vectors if abs(item[0] * axis_y - item[1] * axis_x) <= 0.04
    ]
    non_axial = [item for item in vectors if item not in axial]
    if len(axial) != 4 or len(non_axial) != 3:
        return False
    axial_ratios = sorted(item[2] / contact_radius for item in axial)
    if not all(
        abs(value - expected) <= 0.15
        for value, expected in zip(axial_ratios, (2.0, 2.0, 7.0, 7.0))
    ):
        return False
    non_axial_ratios = sorted(item[2] / contact_radius for item in non_axial)
    if not (
        abs(non_axial_ratios[0] - 5.0) <= 0.15
        and abs(non_axial_ratios[1] - 5.0) <= 0.15
        and 11.0 <= non_axial_ratios[2] <= 11.4
    ):
        return False
    short_diagonals = sorted(non_axial, key=lambda item: item[2])[:2]
    short_centers = [
        ((item[3][0] + item[4][0]) / 2.0, (item[3][1] + item[4][1]) / 2.0)
        for item in short_diagonals
    ]
    if math.hypot(
        short_centers[0][0] - short_centers[1][0],
        short_centers[0][1] - short_centers[1][1],
    ) > contact_radius * 0.08:
        return False
    cross_axis, cross_normal = project(short_centers[0])
    expected_cross_axis = ordered_contacts[1][0] + contact_radius * 10.0
    return (
        abs(cross_axis - expected_cross_axis) <= contact_radius * 0.12
        and abs(cross_normal) <= contact_radius * 0.12
    )


def _has_vertical_two_port_box_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a 1:2 box whose opposite midpoint contacts are isolated ports."""

    if port_count != 2:
        return False
    values = {
        str(value or "").strip()
        for value in shape.get("text_values") or []
        if str(value or "").strip()
    }
    if values != {"1", "2"}:
        return False
    try:
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(contacts) != 2 or len(segments) != 6:
        return False
    radii = [radius for _, radius in contacts]
    contact_radius = sum(radii) / 2.0
    if contact_radius <= 1e-9 or max(radii) / min(radii) > 1.03:
        return False
    axis_dx = contacts[1][0][0] - contacts[0][0][0]
    axis_dy = contacts[1][0][1] - contacts[0][0][1]
    spacing = math.hypot(axis_dx, axis_dy)
    if not 59.8 <= spacing / contact_radius <= 60.2:
        return False
    axis_x, axis_y = axis_dx / spacing, axis_dy / spacing
    normal_x, normal_y = -axis_y, axis_x
    center = (
        (contacts[0][0][0] + contacts[1][0][0]) / 2.0,
        (contacts[0][0][1] + contacts[1][0][1]) / 2.0,
    )
    axial: list[tuple[float, float, float]] = []
    cross: list[tuple[float, float, float]] = []
    for start, end in segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        mx, my = midpoint[0] - center[0], midpoint[1] - center[1]
        axis_position = (mx * axis_x + my * axis_y) / contact_radius
        normal_position = (mx * normal_x + my * normal_y) / contact_radius
        alignment = abs((dx * axis_x + dy * axis_y) / length)
        row = (length / contact_radius, axis_position, normal_position)
        if alignment >= 0.98:
            axial.append(row)
        elif alignment <= 0.02:
            cross.append(row)
        else:
            return False
    if not (len(axial) == 2 and len(cross) == 4):
        return False
    if any(
        abs(length - 60.0) > 0.2
        or abs(axis_position) > 0.1
        or abs(abs(normal_position) - 15.0) > 0.1
        for length, axis_position, normal_position in axial
    ):
        return False
    if any(
        abs(length - 30.0) > 0.2 or abs(normal_position) > 0.1
        for length, _, normal_position in cross
    ):
        return False
    positions = sorted(axis_position for _, axis_position, _ in cross)
    return all(
        abs(actual - expected) <= 0.1
        for actual, expected in zip(positions, (-30.0, -15.0, 15.0, 30.0))
    )


def _has_horizontal_numbered_two_circle_box_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize two numbered circle cells with isolated outward contacts."""

    histogram = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if not (
            port_count == 2
            and int(histogram.get("CIRCLE", 0)) == 2
            and int(histogram.get("LWPOLYLINE", 0)) == 3
            and int(histogram.get("TEXT", 0)) == 2
            and int(histogram.get("LINE", 0)) == 0
            and int(histogram.get("ARC", 0)) == 0
            and int(histogram.get("INSERT", 0)) == 0
        ):
            return False
        values = sorted(
            str(value or "").strip() for value in shape.get("text_values") or []
        )
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius") or item["radius"]),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        rectangles = shape.get("normalized_closed_straight_lwpolylines") or []
        if values != ["1", "2"] or len(contacts) != 2 or len(circles) != 2 or len(rectangles) != 1:
            return False
        edges = [float(value) for value in rectangles[0].get("edge_lengths") or []]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False
    contact_radii = [radius for _, radius in contacts]
    circle_radii = [radius for _, radius in circles]
    if (
        len(edges) != 4
        or min(edges) <= 1e-9
        or min(contact_radii) <= 1e-9
        or min(circle_radii) <= 1e-9
        or max(contact_radii) / min(contact_radii) > 1.03
        or max(circle_radii) / min(circle_radii) > 1.03
    ):
        return False
    edge_groups = sorted(edges)
    if not (
        edge_groups[1] / edge_groups[0] <= 1.03
        and edge_groups[3] / edge_groups[2] <= 1.03
        and 2.45 <= edge_groups[2] / edge_groups[0] <= 2.55
    ):
        return False
    mean_contact_radius = sum(contact_radii) / 2.0
    mean_circle_radius = sum(circle_radii) / 2.0
    if not 4.1 <= mean_circle_radius / mean_contact_radius <= 4.3:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    circle_axis = (
        circles[1][0][0] - circles[0][0][0],
        circles[1][0][1] - circles[0][0][1],
    )
    circle_spacing = math.hypot(*circle_axis)
    if circle_spacing <= 1e-9 or not 3.5 <= circle_spacing / mean_circle_radius <= 3.7:
        return False
    circle_axis = (circle_axis[0] / circle_spacing, circle_axis[1] / circle_spacing)
    used_contacts: set[int] = set()
    offsets: list[tuple[float, float]] = []
    for circle_center, _ in circles:
        nearest = min(
            (
                (distance(circle_center, contact_center), index, contact_center)
                for index, (contact_center, _) in enumerate(contacts)
                if index not in used_contacts
            ),
            key=lambda item: item[0],
        )
        if not 4.9 <= nearest[0] / mean_contact_radius <= 5.1:
            return False
        offset = (
            nearest[2][0] - circle_center[0],
            nearest[2][1] - circle_center[1],
        )
        length = math.hypot(*offset)
        offset = (offset[0] / length, offset[1] / length)
        if abs(offset[0] * circle_axis[0] + offset[1] * circle_axis[1]) > 0.03:
            return False
        offsets.append(offset)
        used_contacts.add(nearest[1])
    return bool(
        len(used_contacts) == 2
        and offsets[0][0] * offsets[1][0] + offsets[0][1] * offsets[1][1] >= 0.99
    )


def _has_named_two_row_box_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize a repeated two-row mechanism enclosed by one 1:2 box."""

    if port_count != 2:
        return False
    histogram = shape.get("entity_histogram") or {}
    try:
        if not (
            int(histogram.get("INSERT", 0)) == 2
            and int(histogram.get("LWPOLYLINE", 0)) == 5
            and int(histogram.get("LINE", 0)) == 0
            and int(histogram.get("ARC", 0)) == 0
            and int(histogram.get("CIRCLE", 0)) == 0
            and int(histogram.get("TEXT", 0)) == 0
        ):
            return False
        bodies = shape.get("normalized_closed_straight_lwpolylines") or []
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        if len(bodies) != 1 or len(contacts) != 4:
            return False
        body = bodies[0]
        vertices = [
            (float(point[0]), float(point[1])) for point in body.get("vertices") or []
        ]
        edge_lengths = [float(value) for value in body.get("edge_lengths") or []]
        body_center = (float(body["center"][0]), float(body["center"][1]))
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(vertices) != 4 or len(edge_lengths) != 4:
        return False
    ordered_edges = sorted(edge_lengths)
    if not (
        ordered_edges[0] > 1e-9
        and abs(ordered_edges[1] - ordered_edges[0]) <= ordered_edges[0] * 0.04
        and abs(ordered_edges[3] - ordered_edges[2]) <= ordered_edges[2] * 0.04
        and 1.95 <= ordered_edges[2] / ordered_edges[0] <= 2.05
    ):
        return False
    contact_radius = sum(radius for _, radius in contacts) / len(contacts)
    if contact_radius <= 1e-9 or any(
        abs(radius - contact_radius) > contact_radius * 0.05
        for _, radius in contacts
    ):
        return False
    if not (
        19.5 <= ordered_edges[0] / contact_radius <= 20.5
        and 39.5 <= ordered_edges[2] / contact_radius <= 40.5
    ):
        return False

    edge_vectors = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        edge_vectors.append((dx / length, dy / length, length))
    short_axis = min(edge_vectors, key=lambda item: item[2])
    axis_x, axis_y = short_axis[0], short_axis[1]
    normal_x, normal_y = -axis_y, axis_x

    projections = []
    for center, _ in contacts:
        dx, dy = center[0] - body_center[0], center[1] - body_center[1]
        projections.append(
            (dx * axis_x + dy * axis_y, dx * normal_x + dy * normal_y)
        )

    def clusters(values: list[float]) -> list[list[float]]:
        result: list[list[float]] = []
        for value in sorted(values):
            if result and abs(value - sum(result[-1]) / len(result[-1])) <= contact_radius * 0.08:
                result[-1].append(value)
            else:
                result.append([value])
        return result

    short_clusters = clusters([item[0] for item in projections])
    long_clusters = clusters([item[1] for item in projections])
    if not (
        len(short_clusters) == 2
        and all(len(group) == 2 for group in short_clusters)
        and len(long_clusters) == 4
        and all(len(group) == 1 for group in long_clusters)
    ):
        return False
    short_values = [sum(group) / len(group) for group in short_clusters]
    long_values = [group[0] for group in long_clusters]
    long_gaps = [
        (long_values[index + 1] - long_values[index]) / contact_radius
        for index in range(3)
    ]
    return (
        4.9 <= abs(short_values[1] - short_values[0]) / contact_radius <= 5.1
        and all(
            abs(value - expected) <= 0.12
            for value, expected in zip(long_gaps, (5.0, 15.0, 5.0))
        )
    )


def _has_single_row_contact_mechanism_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Recognize one repeated component row without using its block name."""

    if port_count != 1:
        return False
    histogram = shape.get("entity_histogram") or {}
    try:
        if not (
            int(histogram.get("CIRCLE", 0)) == 1
            and int(histogram.get("HATCH", 0)) == 1
            and int(histogram.get("LINE", 0)) == 2
            and int(histogram.get("LWPOLYLINE", 0)) == 2
            and int(histogram.get("ARC", 0)) == 0
            and int(histogram.get("TEXT", 0)) == 0
            and int(histogram.get("MTEXT", 0)) == 0
        ):
            return False
        circles = shape.get("normalized_circles") or []
        contacts = shape.get("normalized_closed_bulged_contacts") or []
        segments = shape.get("normalized_line_segments") or []
        if len(circles) != 1 or len(contacts) != 2 or len(segments) != 2:
            return False
        circle_center = (
            float(circles[0]["center"][0]),
            float(circles[0]["center"][1]),
        )
        circle_radius = float(circles[0]["radius"])
        contact_rows = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in contacts
        ]
        line_rows = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if circle_radius <= 1e-9:
        return False
    contact_radius = sum(radius for _, radius in contact_rows) / 2.0
    if (
        contact_radius <= 1e-9
        or any(abs(radius - contact_radius) > contact_radius * 0.06 for _, radius in contact_rows)
        or not 1.9 <= circle_radius / contact_radius <= 2.1
    ):
        return False

    def point_distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    shared = min(
        (
            (point_distance(left, right), left_index, right_index)
            for left_index, left in enumerate(line_rows[0])
            for right_index, right in enumerate(line_rows[1])
        ),
        key=lambda item: item[0],
    )
    if shared[0] > contact_radius * 0.08:
        return False
    shared_point = line_rows[0][shared[1]]
    outer_points = (
        line_rows[0][1 - shared[1]],
        line_rows[1][1 - shared[2]],
    )
    first_vector = (
        outer_points[0][0] - shared_point[0],
        outer_points[0][1] - shared_point[1],
    )
    second_vector = (
        outer_points[1][0] - shared_point[0],
        outer_points[1][1] - shared_point[1],
    )
    first_length = math.hypot(first_vector[0], first_vector[1])
    second_length = math.hypot(second_vector[0], second_vector[1])
    if min(first_length, second_length) <= 1e-9:
        return False
    collinearity = abs(
        first_vector[0] * second_vector[1] - first_vector[1] * second_vector[0]
    ) / (first_length * second_length)
    opposition = (
        first_vector[0] * second_vector[0] + first_vector[1] * second_vector[1]
    ) / (first_length * second_length)
    if collinearity > 0.04 or opposition > -0.98:
        return False

    axis_unit = (
        (outer_points[1][0] - outer_points[0][0])
        / point_distance(outer_points[0], outer_points[1]),
        (outer_points[1][1] - outer_points[0][1])
        / point_distance(outer_points[0], outer_points[1]),
    )
    axis_normal = (-axis_unit[1], axis_unit[0])

    def axis_coordinates(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - circle_center[0], point[1] - circle_center[1]
        return (
            dx * axis_unit[0] + dy * axis_unit[1],
            dx * axis_normal[0] + dy * axis_normal[1],
        )

    contact_coordinates = [axis_coordinates(center) for center, _ in contact_rows]
    inline = [item for item in contact_coordinates if abs(item[1]) <= contact_radius * 0.08]
    offset = [item for item in contact_coordinates if abs(item[1]) > contact_radius * 0.08]
    if len(inline) != 1 or len(offset) != 1:
        return False
    axis_extent = [axis_coordinates(point)[0] for point in outer_points]
    if not min(axis_extent) <= 0.0 <= max(axis_extent):
        return False
    return bool(
        2.4 <= abs(inline[0][0]) / circle_radius <= 2.6
        and abs(offset[0][0]) <= contact_radius * 0.16
        and 2.1 <= abs(offset[0][1]) / circle_radius <= 2.25
    )


def _has_inline_indicator_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the complete line/circle/hatched inline indicator glyph."""

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 6 or len(circles) != 1:
        return False
    circle_center, circle_radius = circles[0]
    if circle_radius <= 1e-9:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    measured = sorted(
        (
            distance(start, end),
            start,
            end,
        )
        for start, end in segments
    )
    dominant_length, dominant_start, dominant_end = measured[-1]
    if not 31.8 <= dominant_length / circle_radius <= 32.2:
        return False
    axis_x = (dominant_end[0] - dominant_start[0]) / dominant_length
    axis_y = (dominant_end[1] - dominant_start[1]) / dominant_length
    normal_x, normal_y = -axis_y, axis_x
    circle_dx = circle_center[0] - dominant_start[0]
    circle_dy = circle_center[1] - dominant_start[1]
    circle_axis = circle_dx * axis_x + circle_dy * axis_y
    circle_normal = circle_dx * normal_x + circle_dy * normal_y
    if abs(circle_normal) > circle_radius * 0.03:
        return False
    if not 0.42 <= min(circle_axis, dominant_length - circle_axis) / dominant_length <= 0.44:
        return False

    marker_length, marker_start, marker_end = measured[-2]
    if not 4.43 <= marker_length / circle_radius <= 4.51:
        return False
    marker_midpoint = (
        (marker_start[0] + marker_end[0]) / 2.0,
        (marker_start[1] + marker_end[1]) / 2.0,
    )
    marker_dx = marker_midpoint[0] - circle_center[0]
    marker_dy = marker_midpoint[1] - circle_center[1]
    marker_axis = marker_dx * axis_x + marker_dy * axis_y
    marker_normal = marker_dx * normal_x + marker_dy * normal_y
    marker_vector = (
        marker_end[0] - marker_start[0],
        marker_end[1] - marker_start[1],
    )
    marker_alignment = abs(
        (marker_vector[0] * axis_x + marker_vector[1] * axis_y) / marker_length
    )
    if not (
        6.9 <= abs(marker_axis) / circle_radius <= 7.15
        and abs(marker_normal) <= circle_radius * 0.05
        and 0.43 <= marker_alignment <= 0.47
    ):
        return False

    mechanism = measured[:4]
    ratios = [length / circle_radius for length, _, _ in mechanism]
    expected = (0.824621, 0.824621, 1.8, 1.8)
    if any(abs(actual - target) > 0.04 for actual, target in zip(ratios, expected)):
        return False
    if any(
        distance(point, circle_center) > circle_radius * 1.26
        for _, start, end in mechanism
        for point in (start, end)
    ):
        return False

    short_segments = mechanism[:2]
    long_segments = mechanism[2:]
    used_long: set[int] = set()
    for _, short_start, short_end in short_segments:
        matches = sorted(
            (
                distance(short_point, long_point),
                long_index,
            )
            for short_point in (short_start, short_end)
            for long_index, (_, long_start, long_end) in enumerate(long_segments)
            for long_point in (long_start, long_end)
        )
        if not matches or matches[0][0] > circle_radius * 0.03:
            return False
        used_long.add(matches[0][1])
    return used_long == {0, 1}


def _has_crossed_two_contact_open_switch_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize an X-marked two-contact switch without inferring conductivity."""

    try:
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        leads = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        diagonals = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_open_lwpolyline_segments") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(contacts) != 2 or len(leads) != 2 or len(diagonals) != 2:
        return False
    contact_radius = sum(radius for _, radius in contacts) / 2.0
    if contact_radius <= 1e-9 or any(
        abs(radius - contact_radius) > contact_radius * 0.04
        for _, radius in contacts
    ):
        return False
    axis_dx = contacts[1][0][0] - contacts[0][0][0]
    axis_dy = contacts[1][0][1] - contacts[0][0][1]
    contact_spacing = math.hypot(axis_dx, axis_dy)
    if not 19.8 <= contact_spacing / contact_radius <= 20.2:
        return False
    axis_x, axis_y = axis_dx / contact_spacing, axis_dy / contact_spacing
    normal_x, normal_y = -axis_y, axis_x
    center = (
        (contacts[0][0][0] + contacts[1][0][0]) / 2.0,
        (contacts[0][0][1] + contacts[1][0][1]) / 2.0,
    )

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    used_contacts: set[int] = set()
    for start, end in leads:
        matches = sorted(
            (
                distance(endpoint, contact),
                endpoint_index,
                contact_index,
            )
            for endpoint_index, endpoint in enumerate((start, end))
            for contact_index, (contact, _) in enumerate(contacts)
        )
        nearest_distance, endpoint_index, contact_index = matches[0]
        if nearest_distance > contact_radius * 0.04 or contact_index in used_contacts:
            return False
        outer = (start, end)[endpoint_index]
        inner = (start, end)[1 - endpoint_index]
        dx, dy = inner[0] - outer[0], inner[1] - outer[1]
        length = math.hypot(dx, dy)
        toward_center = (
            (center[0] - outer[0]) * dx + (center[1] - outer[1]) * dy
        )
        if not 3.9 <= length / contact_radius <= 4.1 or toward_center <= 0.0:
            return False
        if abs(dx * normal_x + dy * normal_y) > contact_radius * 0.04:
            return False
        used_contacts.add(contact_index)
    if used_contacts != {0, 1}:
        return False

    diagonal_slopes = []
    for start, end in diagonals:
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        if distance(midpoint, center) > contact_radius * 0.05:
            return False
        projections = []
        for point in (start, end):
            dx, dy = point[0] - center[0], point[1] - center[1]
            projections.append(
                (
                    (dx * axis_x + dy * axis_y) / contact_radius,
                    (dx * normal_x + dy * normal_y) / contact_radius,
                )
            )
        if any(
            abs(abs(axis_value) - 3.6) > 0.12
            or abs(abs(normal_value) - 4.8) > 0.12
            for axis_value, normal_value in projections
        ):
            return False
        dx, dy = end[0] - start[0], end[1] - start[1]
        diagonal_slopes.append(
            (dx * axis_x + dy * axis_y) * (dx * normal_x + dy * normal_y)
        )
    return diagonal_slopes[0] * diagonal_slopes[1] < 0.0


def _has_bare_diode_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the triangle/bar/lead relationship without an orientation."""
    if shape.get("diode_bare_topology") is True or shape.get("diode_symbol_topology") == "bare":
        return True
    segments = shape.get("normalized_line_segments") or []
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if len(segments) != 5 or len(contacts) != 2:
        return False
    try:
        contact_centers = [
            (float(item["center"][0]), float(item["center"][1]))
            for item in contacts
        ]
        parsed_segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in segments
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    axis_x = contact_centers[1][0] - contact_centers[0][0]
    axis_y = contact_centers[1][1] - contact_centers[0][1]
    axis_length = math.hypot(axis_x, axis_y)
    if axis_length <= 1e-9:
        return False
    axis_x, axis_y = axis_x / axis_length, axis_y / axis_length

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    classified = []
    for start, end in parsed_segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        alignment = abs((dx / length) * axis_x + (dy / length) * axis_y)
        kind = "axial" if alignment >= 0.95 else "bar" if alignment <= 0.1 else "diagonal"
        classified.append((kind, start, end))
    axial = [item for item in classified if item[0] == "axial"]
    bars = [item for item in classified if item[0] == "bar"]
    diagonals = [item for item in classified if item[0] == "diagonal"]
    if not (len(axial) == 1 and len(bars) == 2 and len(diagonals) == 2):
        return False
    lead_start, lead_end = axial[0][1], axial[0][2]
    if min(
        distance(lead_start, contact_centers[0]) + distance(lead_end, contact_centers[1]),
        distance(lead_start, contact_centers[1]) + distance(lead_end, contact_centers[0]),
    ) > 0.08:
        return False
    first_points = (diagonals[0][1], diagonals[0][2])
    second_points = (diagonals[1][1], diagonals[1][2])
    left_shared, right_shared, shared_gap = min(
        (
            (left_index, right_index, distance(left, right))
            for left_index, left in enumerate(first_points)
            for right_index, right in enumerate(second_points)
        ),
        key=lambda item: item[2],
    )
    if shared_gap > 0.04:
        return False
    outer_points = (
        first_points[1 - left_shared],
        second_points[1 - right_shared],
    )
    return any(
        min(
            distance(outer_points[0], bar[1]) + distance(outer_points[1], bar[2]),
            distance(outer_points[0], bar[2]) + distance(outer_points[1], bar[1]),
        ) <= 0.08
        for bar in bars
    )


def _has_boxed_diode_topology(shape: Mapping[str, Any]) -> bool:
    """Require explicit/repeated diode evidence for the boxed graphic."""
    if shape.get("boxed_diode_repeated_topology") is True:
        return True
    if shape.get("diode_symbol_topology") == "boxed_repeated":
        return True
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    segments = shape.get("normalized_line_segments") or []
    if len(contacts) != 2 or len(segments) != 13:
        return False
    return bool(
        shape.get("boxed_diode_repeated_topology") is True
        or (
            shape.get("repeated_diode_count") == 2
            and shape.get("outer_box_topology") is True
        )
    )


def _has_wire_crossover_jump_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize two outward collinear leads bound to a semicircular arc."""
    try:
        lines = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        arcs = shape.get("normalized_arcs") or []
        if len(lines) != 2 or len(arcs) != 1:
            return False
        arc = arcs[0]
        center = (float(arc["center"][0]), float(arc["center"][1]))
        radius = float(arc["radius"])
        if radius <= 1e-9 or abs(float(arc.get("sweep_deg", 0.0)) - 180.0) > 1.0:
            return False
    except (KeyError, IndexError, TypeError, ValueError):
        return False

    near_and_far = []
    tolerance = max(radius * 0.03, 1e-6)
    for start, end in lines:
        start_radius = math.hypot(start[0] - center[0], start[1] - center[1])
        end_radius = math.hypot(end[0] - center[0], end[1] - center[1])
        if abs(start_radius - radius) <= tolerance and end_radius > radius + tolerance:
            near_and_far.append((start, end))
        elif abs(end_radius - radius) <= tolerance and start_radius > radius + tolerance:
            near_and_far.append((end, start))
        else:
            return False
    (near_left, far_left), (near_right, far_right) = near_and_far
    left_vector = (near_left[0] - center[0], near_left[1] - center[1])
    right_vector = (near_right[0] - center[0], near_right[1] - center[1])
    if math.hypot(near_left[0] - near_right[0], near_left[1] - near_right[1]) < 1.9 * radius:
        return False
    if left_vector[0] * right_vector[0] + left_vector[1] * right_vector[1] > -0.9 * radius * radius:
        return False
    for near, far, radial in (
        (near_left, far_left, left_vector),
        (near_right, far_right, right_vector),
    ):
        lead = (far[0] - near[0], far[1] - near[1])
        lead_length = math.hypot(*lead)
        if lead_length <= tolerance:
            return False
        cross = abs(lead[0] * radial[1] - lead[1] * radial[0])
        if cross > 0.03 * lead_length * radius:
            return False
        if lead[0] * radial[0] + lead[1] * radial[1] <= 0:
            return False
    return True


def _has_circle_contact_marker_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize one barred circle radially linked to one smaller round marker."""

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 2 or len(circles) != 1 or len(contacts) != 1:
        return False
    circle_center, circle_radius = circles[0]
    contact_center, contact_radius = contacts[0]
    if min(circle_radius, contact_radius) <= 1e-9:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    if not (
        1.95 <= circle_radius / contact_radius <= 2.05
        and 2.45 <= distance(circle_center, contact_center) / circle_radius <= 2.55
    ):
        return False

    diameter_candidates = []
    connector_candidates = []
    for start, end in segments:
        length = distance(start, end)
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        if (
            1.95 <= length / circle_radius <= 2.05
            and distance(midpoint, circle_center) <= circle_radius * 0.03
            and all(
                0.97 <= distance(point, circle_center) / circle_radius <= 1.03
                for point in (start, end)
            )
        ):
            diameter_candidates.append((start, end, length))
        contact_end = min((start, end), key=lambda point: distance(point, contact_center))
        circle_end = end if contact_end is start else start
        if (
            1.45 <= length / circle_radius <= 1.55
            and distance(contact_end, contact_center) <= circle_radius * 0.03
            and 0.97 <= distance(circle_end, circle_center) / circle_radius <= 1.03
        ):
            connector_candidates.append((circle_end, contact_end, length))
    if len(diameter_candidates) != 1 or len(connector_candidates) != 1:
        return False

    diameter_start, diameter_end, diameter_length = diameter_candidates[0]
    circle_end, contact_end, connector_length = connector_candidates[0]
    diameter_axis = (
        (diameter_end[0] - diameter_start[0]) / diameter_length,
        (diameter_end[1] - diameter_start[1]) / diameter_length,
    )
    connector_axis = (
        (contact_end[0] - circle_end[0]) / connector_length,
        (contact_end[1] - circle_end[1]) / connector_length,
    )
    radial = (
        (contact_center[0] - circle_center[0]) / distance(circle_center, contact_center),
        (contact_center[1] - circle_center[1]) / distance(circle_center, contact_center),
    )
    return bool(
        abs(diameter_axis[0] * connector_axis[0] + diameter_axis[1] * connector_axis[1]) <= 0.03
        and connector_axis[0] * radial[0] + connector_axis[1] * radial[1] >= 0.99
        and distance(
            circle_end,
            (
                circle_center[0] + radial[0] * circle_radius,
                circle_center[1] + radial[1] * circle_radius,
            ),
        ) <= circle_radius * 0.03
    )


def _has_crossed_circle_opposed_contacts_ignore_topology(
    shape: Mapping[str, Any],
) -> bool:
    """Recognize a circle with an inscribed X and two opposed side regions.

    All checks use relative distances and dot products.  The rule is thus
    invariant to definition translation, rotation, reflection, and uniform
    scale while remaining strict about the complete five-entity topology.
    """

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 2 or len(circles) != 1 or len(contacts) != 2:
        return False

    circle_center, circle_radius = circles[0]
    contact_radii = [radius for _, radius in contacts]
    if circle_radius <= 1e-9 or min(contact_radii) <= 1e-9:
        return False
    mean_contact_radius = sum(contact_radii) / 2.0
    if (
        max(contact_radii) / min(contact_radii) > 1.03
        or not 0.255 <= mean_contact_radius / circle_radius <= 0.278
    ):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    contact_centers = [center for center, _ in contacts]
    contact_spacing = distance(contact_centers[0], contact_centers[1])
    if contact_spacing <= 1e-9:
        return False
    contact_midpoint = (
        (contact_centers[0][0] + contact_centers[1][0]) / 2.0,
        (contact_centers[0][1] + contact_centers[1][1]) / 2.0,
    )
    if not (
        1.98 <= contact_spacing / circle_radius <= 2.02
        and distance(contact_midpoint, circle_center) <= circle_radius * 0.02
        and all(
            0.98 <= distance(center, circle_center) / circle_radius <= 1.02
            for center in contact_centers
        )
    ):
        return False
    contact_axis = (
        (contact_centers[1][0] - contact_centers[0][0]) / contact_spacing,
        (contact_centers[1][1] - contact_centers[0][1]) / contact_spacing,
    )

    diameter_axes: list[tuple[float, float]] = []
    for start, end in segments:
        length = distance(start, end)
        if length <= 1e-9:
            return False
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        if not (
            1.98 <= length / circle_radius <= 2.02
            and distance(midpoint, circle_center) <= circle_radius * 0.02
            and all(
                0.98 <= distance(point, circle_center) / circle_radius <= 1.02
                for point in (start, end)
            )
        ):
            return False
        diameter_axes.append(
            ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
        )
    if abs(
        diameter_axes[0][0] * diameter_axes[1][0]
        + diameter_axes[0][1] * diameter_axes[1][1]
    ) > 0.03:
        return False

    # The opposed side-region axis bisects both perpendicular diameters.  This
    # rejects an ordinary circled plus and offset same-count contact drawings.
    return all(
        0.69
        <= abs(axis[0] * contact_axis[0] + axis[1] * contact_axis[1])
        <= 0.72
        for axis in diameter_axes
    )


def _has_actuated_open_switch_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the complete PWF192 two-contact actuated open switch.

    The two equal closed contact regions establish a local frame and scale.
    All seven undirected LINE segments are then matched as a multiset in that
    frame, including the duplicated actuator strut.  Trying both contact
    orders and both frame handednesses makes the rule invariant to rotation,
    reflection, and uniform scale without using a name or fingerprint.
    """

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 7 or len(contacts) != 2:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    contact_spacing = distance(contacts[0][0], contacts[1][0])
    contact_radii = [radius for _, radius in contacts]
    if (
        contact_spacing <= 1e-9
        or min(contact_radii) <= 1e-9
        or max(contact_radii) / min(contact_radii) > 1.03
        or not 0.042 <= sum(contact_radii) / 2.0 / contact_spacing <= 0.047
    ):
        return False

    expected_segments = [
        ((-0.5, 0.0), (-1.0 / 6.0, 0.0)),
        ((0.5, 0.0), (1.0 / 6.0, 0.0)),
        ((1.0 / 6.0, 0.0), (-4.0 / 15.0, -5.0 / 24.0)),
        ((-1.0 / 8.0, 1.0 / 3.0), (0.0, 0.5)),
        ((-1.0 / 8.0, 1.0 / 3.0), (0.0, 0.5)),
        ((0.0, 1.0 / 3.0), (-1.0 / 8.0, 1.0 / 3.0)),
        ((0.0, 0.5), (0.0, -0.0801)),
    ]

    def segment_matches(
        actual: tuple[tuple[float, float], tuple[float, float]],
        expected: tuple[tuple[float, float], tuple[float, float]],
    ) -> bool:
        direct = max(
            distance(actual[0], expected[0]), distance(actual[1], expected[1])
        )
        reversed_distance = max(
            distance(actual[0], expected[1]), distance(actual[1], expected[0])
        )
        return min(direct, reversed_distance) <= 0.012

    for first_index, second_index in ((0, 1), (1, 0)):
        first_center = contacts[first_index][0]
        second_center = contacts[second_index][0]
        origin = (
            (first_center[0] + second_center[0]) / 2.0,
            (first_center[1] + second_center[1]) / 2.0,
        )
        axis = (
            (second_center[0] - first_center[0]) / contact_spacing,
            (second_center[1] - first_center[1]) / contact_spacing,
        )
        for handedness in (-1.0, 1.0):
            perpendicular = (-axis[1] * handedness, axis[0] * handedness)

            def normalize(point: tuple[float, float]) -> tuple[float, float]:
                relative = (point[0] - origin[0], point[1] - origin[1])
                return (
                    (relative[0] * axis[0] + relative[1] * axis[1])
                    / contact_spacing,
                    (
                        relative[0] * perpendicular[0]
                        + relative[1] * perpendicular[1]
                    )
                    / contact_spacing,
                )

            normalized_segments = [
                (normalize(start), normalize(end)) for start, end in segments
            ]
            unused = list(normalized_segments)
            for expected in expected_segments:
                match_index = next(
                    (
                        index
                        for index, actual in enumerate(unused)
                        if segment_matches(actual, expected)
                    ),
                    None,
                )
                if match_index is None:
                    break
                unused.pop(match_index)
            else:
                return not unused
    return False


def _has_pwf172_led_arrow_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """PWF172: complete LED/diode arrow artwork, not two terminals."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if (int(h.get("LINE", 0)) != 7 or int(h.get("LWPOLYLINE", 0)) != 4
                or int(h.get("ARC", 0)) or int(h.get("CIRCLE", 0))
                or int(shape.get("text_count", 0))
                or len(shape.get("normalized_closed_bulged_contacts") or []) != 2
                or len(shape.get("normalized_open_lwpolylines") or []) != 2):
            return False
        contacts = shape["normalized_closed_bulged_contacts"]
        radii = [float(c.get("chord_radius", c["radius"])) for c in contacts]
        if min(radii) <= 0 or max(radii) / min(radii) > 1.03:
            return False
        paths = shape["normalized_open_lwpolylines"]
        if any(len(p.get("vertices") or []) != 2 for p in paths):
            return False
        for path in paths:
            vertices = path["vertices"]
            if any(abs(float(v.get("bulge", 0))) > 1e-9 for v in vertices):
                return False
            widths = [float(v.get("start_width", 0)) for v in vertices] + [float(v.get("end_width", 0)) for v in vertices]
            positive_widths = [width for width in widths if width > 1e-9]
            if (
                len(positive_widths) != 3
                or max(positive_widths) / min(positive_widths) > 1.03
                or sum(width <= 1e-9 for width in widths) != 1
            ):
                return False
        segments = list(shape.get("normalized_line_segments") or []) + list(
            shape.get("normalized_open_lwpolyline_segments") or []
        )
        template = (
            ((.447932, .442724), (.239662, .650994)),
            ((.552068, .546859), (.343797, .75513)),
            ((.708333, 0.0), (.708333, .416667)),
            ((.291667, 0.0), (.291667, .416667)),
            ((.291667, 0.0), (.708145, .208333)),
            ((.708145, .208333), (.291667, .416667)),
            ((.083333, .208333), (.916415, .208333)),
            ((.239662, .650994), (.343797, .546859)),
            ((.343797, .75513), (.447932, .650994)),
        )
        return (
            len(segments) == 9
            and _segments_match_similarity(segments, template, relative_tolerance=.018)
            and math.dist(contacts[0]["center"], contacts[1]["center"])
            > max(radii) * 8
        )
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_pwf216_narrow_frame_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """PWF216: narrow vertical frame and slanted base, wholly visual."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    try:
        if (int(h.get("LINE", 0)) != 3 or int(h.get("LWPOLYLINE", 0)) != 4
                or int(h.get("ARC", 0)) or int(h.get("CIRCLE", 0))
                or int(shape.get("text_count", 0))
                or len(shape.get("normalized_closed_bulged_contacts") or []) != 2
                or len(shape.get("normalized_closed_straight_lwpolylines") or []) != 2):
            return False
        contacts = shape["normalized_closed_bulged_contacts"]
        radii = [float(c.get("chord_radius", c["radius"])) for c in contacts]
        if min(radii) <= 0 or max(radii) / min(radii) > 1.03:
            return False
        rectangles = shape["normalized_closed_straight_lwpolylines"]
        if any(len(r.get("vertices") or []) != 4 for r in rectangles):
            return False
        segments = list(shape.get("normalized_line_segments") or [])
        for rectangle in rectangles:
            vertices = rectangle["vertices"]
            segments.extend(
                {"start": vertices[index], "end": vertices[(index + 1) % 4]}
                for index in range(4)
            )
        template = (
            ((.346939, .153061), (.653061, 0.0)),
            ((.040816, .459184), (.346939, .459184)),
            ((.653061, .459184), (.959184, .459184)),
            ((.346939, .153061), (.653061, .153061)),
            ((.653061, .153061), (.653061, 0.0)),
            ((.653061, 0.0), (.346939, 0.0)),
            ((.346939, 0.0), (.346939, .153061)),
            ((.346939, .765306), (.653061, .765306)),
            ((.653061, .765306), (.653061, .153061)),
            ((.653061, .153061), (.346939, .153061)),
            ((.346939, .153061), (.346939, .765306)),
        )
        return (
            len(segments) == 11
            and _segments_match_similarity(segments, template, relative_tolerance=.018)
            and math.dist(contacts[0]["center"], contacts[1]["center"])
            > max(radii) * 20
        )
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _has_wide_contact_cap_marker_ignore_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the complete PWF10 open-wide-polyline/contact-area motif."""

    try:
        contacts = shape.get("normalized_closed_bulged_contacts") or []
        open_polylines = shape.get("normalized_open_lwpolylines") or []
        if len(contacts) != 1 or len(open_polylines) != 1:
            return False
        contact = contacts[0]
        contact_center = (
            float(contact["center"][0]),
            float(contact["center"][1]),
        )
        contact_radius = float(contact.get("chord_radius", contact["radius"]))
        if contact.get("invisible") is not True or contact_radius <= 1e-9:
            return False
        polyline = open_polylines[0]
        if polyline.get("invisible") is not False:
            return False
        vertices = [
            {
                "point": (float(item["point"][0]), float(item["point"][1])),
                "start_width": float(item["start_width"]),
                "end_width": float(item["end_width"]),
                "bulge": float(item["bulge"]),
            }
            for item in polyline.get("vertices") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(vertices) != 3 or any(abs(item["bulge"]) > 1e-9 for item in vertices):
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    if distance(vertices[0]["point"], contact_center) > contact_radius * 0.02:
        return False
    axis_vector = (
        vertices[0]["point"][0] - vertices[1]["point"][0],
        vertices[0]["point"][1] - vertices[1]["point"][1],
    )
    axis_length = math.hypot(*axis_vector)
    if axis_length <= 1e-9:
        return False
    axis = (axis_vector[0] / axis_length, axis_vector[1] / axis_length)
    expected_positions = (0.0, -13.0, -5.0)
    for vertex, expected_position in zip(vertices, expected_positions):
        relative = (
            vertex["point"][0] - contact_center[0],
            vertex["point"][1] - contact_center[1],
        )
        projection = (relative[0] * axis[0] + relative[1] * axis[1]) / contact_radius
        perpendicular = abs(relative[0] * axis[1] - relative[1] * axis[0]) / contact_radius
        if abs(projection - expected_position) > 0.04 or perpendicular > 0.02:
            return False

    widths = [
        (vertex["start_width"] / contact_radius, vertex["end_width"] / contact_radius)
        for vertex in vertices
    ]
    if not (
        max(abs(value) for value in widths[0]) <= 0.02
        and all(
            abs(value - 2.0) <= 0.04
            for pair in widths[1:]
            for value in pair
        )
    ):
        return False
    return bool(
        12.98
        <= distance(vertices[0]["point"], vertices[1]["point"])
        / contact_radius
        <= 13.02
        and 7.98
        <= distance(vertices[1]["point"], vertices[2]["point"])
        / contact_radius
        <= 8.02
    )


def _has_dzb_right_marker_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the doubled stepped-bar DZB marker by relative topology."""

    def parse_segments(key: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        result = []
        try:
            for item in shape.get(key) or []:
                result.append(
                    (
                        (float(item["start"][0]), float(item["start"][1])),
                        (float(item["end"][0]), float(item["end"][1])),
                    )
                )
        except (KeyError, IndexError, TypeError, ValueError):
            return []
        return result

    lines = parse_segments("normalized_line_segments")
    polylines = parse_segments("normalized_open_lwpolyline_segments")
    if len(lines) != 6 or len(polylines) != 3:
        return False

    def vector(segment: tuple[tuple[float, float], tuple[float, float]]) -> tuple[float, float, float]:
        (sx, sy), (ex, ey) = segment
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError("degenerate segment")
        return dx / length, dy / length, length

    def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def coincident(
        left: tuple[tuple[float, float], tuple[float, float]],
        right: tuple[tuple[float, float], tuple[float, float]],
        tolerance: float = 0.012,
    ) -> bool:
        return min(
            max(distance(left[0], right[0]), distance(left[1], right[1])),
            max(distance(left[0], right[1]), distance(left[1], right[0])),
        ) <= tolerance

    matched_indices: list[int] = []
    for polyline in polylines:
        matches = [index for index, line in enumerate(lines) if coincident(polyline, line)]
        if len(matches) != 1 or matches[0] in matched_indices:
            return False
        matched_indices.append(matches[0])
    bars = [lines[index] for index in matched_indices]
    try:
        bar_vectors = [vector(bar) for bar in bars]
    except ValueError:
        return False
    reference_x, reference_y, longest = max(bar_vectors, key=lambda item: item[2])
    if any(abs(reference_x * dy - reference_y * dx) > 0.04 for dx, dy, _ in bar_vectors):
        return False
    ordered = sorted(
        zip(bars, bar_vectors, strict=True), key=lambda item: item[1][2], reverse=True
    )
    ratios = [item[1][2] / longest for item in ordered]
    if not (0.57 <= ratios[1] <= 0.63 and 0.17 <= ratios[2] <= 0.23):
        return False
    centers = [
        ((bar[0][0] + bar[1][0]) / 2.0, (bar[0][1] + bar[1][1]) / 2.0)
        for bar, _ in ordered
    ]
    axis_positions = [center[0] * reference_x + center[1] * reference_y for center in centers]
    if max(axis_positions) - min(axis_positions) > longest * 0.025:
        return False
    normal_positions = [center[0] * -reference_y + center[1] * reference_x for center in centers]
    steps = sorted(
        abs(normal_positions[index] - normal_positions[0]) / longest for index in (1, 2)
    )
    if not (0.17 <= steps[0] <= 0.23 and 0.37 <= steps[1] <= 0.43):
        return False

    remaining = [line for index, line in enumerate(lines) if index not in matched_indices]
    duplicate_pairs = [
        (left, right)
        for left in range(len(remaining))
        for right in range(left + 1, len(remaining))
        if coincident(remaining[left], remaining[right])
    ]
    if len(duplicate_pairs) != 1:
        return False
    stem_left, stem_right = duplicate_pairs[0]
    stem = remaining[stem_left]
    side_leads = [
        segment for index, segment in enumerate(remaining) if index not in {stem_left, stem_right}
    ]
    if len(side_leads) != 1:
        return False
    side_lead = side_leads[0]
    try:
        stem_x, stem_y, stem_length = vector(stem)
        side_x, side_y, side_length = vector(side_lead)
    except ValueError:
        return False
    if abs(stem_x * reference_x + stem_y * reference_y) > 0.05:
        return False
    if abs(side_x * reference_y - side_y * reference_x) > 0.05:
        return False
    if not (0.57 <= stem_length / longest <= 0.63 and 0.47 <= side_length / longest <= 0.53):
        return False

    longest_center = centers[0]
    attached_stem_end = min(stem, key=lambda point: distance(point, longest_center))
    outer_stem_end = max(stem, key=lambda point: distance(point, longest_center))
    return (
        distance(attached_stem_end, longest_center) <= longest * 0.025
        and min(distance(side_lead[0], outer_stem_end), distance(side_lead[1], outer_stem_end))
        <= longest * 0.025
    )


def _has_contact_led_stepped_ground_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize duplicated stepped bars joined to one round GND contact."""

    def parse(key: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        try:
            return [
                (
                    (float(item["start"][0]), float(item["start"][1])),
                    (float(item["end"][0]), float(item["end"][1])),
                )
                for item in shape.get(key) or []
            ]
        except (KeyError, IndexError, TypeError, ValueError):
            return []

    lines = parse("normalized_line_segments")
    polylines = parse("normalized_open_lwpolyline_segments")
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if len(lines) != 4 or len(polylines) != 3 or len(contacts) != 1:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    def coincident(left, right) -> bool:
        return min(
            max(distance(left[0], right[0]), distance(left[1], right[1])),
            max(distance(left[0], right[1]), distance(left[1], right[0])),
        ) <= 0.015

    matched_indices: list[int] = []
    for polyline in polylines:
        matches = [index for index, line in enumerate(lines) if coincident(polyline, line)]
        if len(matches) != 1 or matches[0] in matched_indices:
            return False
        matched_indices.append(matches[0])
    bars = [lines[index] for index in matched_indices]

    def vector(segment):
        dx = segment[1][0] - segment[0][0]
        dy = segment[1][1] - segment[0][1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError("degenerate segment")
        return dx / length, dy / length, length

    try:
        bar_vectors = [vector(bar) for bar in bars]
    except ValueError:
        return False
    longest_index = max(range(3), key=lambda index: bar_vectors[index][2])
    reference_x, reference_y, longest = bar_vectors[longest_index]
    if any(
        abs(reference_x * direction_y - reference_y * direction_x) > 0.04
        for direction_x, direction_y, _ in bar_vectors
    ):
        return False
    lengths = sorted((item[2] for item in bar_vectors), reverse=True)
    if not (
        0.55 <= lengths[1] / longest <= 0.65
        and 0.15 <= lengths[2] / longest <= 0.25
    ):
        return False
    centers = [
        ((bar[0][0] + bar[1][0]) / 2.0, (bar[0][1] + bar[1][1]) / 2.0)
        for bar in bars
    ]
    axial = [center[0] * reference_x + center[1] * reference_y for center in centers]
    if max(axial) - min(axial) > longest * 0.03:
        return False
    normal_x, normal_y = -reference_y, reference_x
    longest_normal = centers[longest_index][0] * normal_x + centers[longest_index][1] * normal_y
    steps = sorted(
        abs(center[0] * normal_x + center[1] * normal_y - longest_normal) / longest
        for index, center in enumerate(centers)
        if index != longest_index
    )
    if not (0.15 <= steps[0] <= 0.23 and 0.32 <= steps[1] <= 0.43):
        return False

    remaining = [line for index, line in enumerate(lines) if index not in matched_indices]
    if len(remaining) != 1:
        return False
    lead = remaining[0]
    try:
        lead_x, lead_y, lead_length = vector(lead)
        contact_center = (
            float(contacts[0]["center"][0]),
            float(contacts[0]["center"][1]),
        )
        contact_radius = float(contacts[0]["radius"])
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    longest_center = centers[longest_index]
    return bool(
        abs(lead_x * reference_x + lead_y * reference_y) <= 0.05
        and 0.49 <= lead_length / longest <= 0.62
        and min(distance(lead[0], longest_center), distance(lead[1], longest_center))
        <= longest * 0.03
        and min(distance(lead[0], contact_center), distance(lead[1], contact_center))
        <= longest * 0.03
        and 0.07 <= contact_radius / longest <= 0.12
    )


def _has_repeated_stepped_ground_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the six-LINE/three-open-LWPOLYLINE stepped ground glyph."""
    def parse(key: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        try:
            return [((float(x["start"][0]), float(x["start"][1])),
                     (float(x["end"][0]), float(x["end"][1]))) for x in shape.get(key) or []]
        except (KeyError, IndexError, TypeError, ValueError):
            return []
    lines, polylines = parse("normalized_line_segments"), parse("normalized_open_lwpolyline_segments")
    if len(lines) != 6 or len(polylines) != 3:
        return False
    def vec(s):
        dx, dy = s[1][0] - s[0][0], s[1][1] - s[0][1]
        length = math.hypot(dx, dy)
        return (dx / length, dy / length, length) if length > 1e-9 else None
    def dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
    def same(a, b):
        return min(max(dist(a[0], b[0]), dist(a[1], b[1])), max(dist(a[0], b[1]), dist(a[1], b[0]))) <= .012
    matches = []
    for p in polylines:
        found = [i for i, line in enumerate(lines) if same(p, line)]
        if len(found) != 1 or found[0] in matches: return False
        matches.append(found[0])
    bars = [lines[i] for i in matches]
    vectors = [vec(s) for s in bars]
    if any(v is None for v in vectors): return False
    ref = max(vectors, key=lambda v: v[2])
    if any(abs(ref[0] * v[1] - ref[1] * v[0]) > .04 for v in vectors): return False
    lengths = sorted((v[2] for v in vectors), reverse=True)
    if not (.62 <= lengths[1] / lengths[0] <= .78 and .35 <= lengths[2] / lengths[0] <= .58): return False
    centers = [((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2) for s in bars]
    axis = [c[0] * ref[0] + c[1] * ref[1] for c in centers]
    normal = [c[0] * -ref[1] + c[1] * ref[0] for c in centers]
    if max(axis) - min(axis) > lengths[0] * .025: return False
    steps = sorted(abs(n - normal[0]) / lengths[0] for n in normal[1:])
    if not (.12 <= steps[0] <= .35 and .25 <= steps[1] <= .65): return False
    remaining = [line for i, line in enumerate(lines) if i not in matches]
    if len(remaining) != 3 or not same(remaining[0], remaining[1]): return False
    stem, lead = remaining[0], remaining[2]
    sv, lv = vec(stem), vec(lead)
    if sv is None or lv is None: return False
    if abs(sv[0] * ref[0] + sv[1] * ref[1]) > .05: return False
    if abs(lv[0] * ref[1] - lv[1] * ref[0]) > .05: return False
    longest_center = centers[vectors.index(max(vectors, key=lambda v: v[2]))]
    stem_end = min(stem, key=lambda p: dist(p, longest_center))
    outer = max(stem, key=lambda p: dist(p, longest_center))
    return (dist(stem_end, longest_center) <= lengths[0] * .04 and
            min(dist(lead[0], outer), dist(lead[1], outer)) <= lengths[0] * .04 and
            .45 <= sv[2] / lengths[0] <= .9 and .3 <= lv[2] / lengths[0] <= .8)


def _has_circled_stepped_ground_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize PWF314's circled stepped-bar ground marker geometrically."""

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 4 or len(contacts) != 1 or len(circles) != 1:
        return False

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    def vector(segment):
        dx = segment[1][0] - segment[0][0]
        dy = segment[1][1] - segment[0][1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError("degenerate segment")
        return dx / length, dy / length, length

    contact_center, contact_radius = contacts[0]
    circle_center, circle_radius = circles[0]
    if contact_radius <= 0.0 or circle_radius <= 0.0:
        return False

    for lead_index, lead in enumerate(segments):
        bars = [segment for index, segment in enumerate(segments) if index != lead_index]
        try:
            lead_dx, lead_dy, lead_length = vector(lead)
            bar_vectors = [vector(bar) for bar in bars]
        except ValueError:
            continue

        longest_index = max(range(3), key=lambda index: bar_vectors[index][2])
        reference_dx, reference_dy, longest = bar_vectors[longest_index]
        if any(
            abs(reference_dx * dy - reference_dy * dx) > 0.035
            for dx, dy, _ in bar_vectors
        ):
            continue
        if abs(lead_dx * reference_dx + lead_dy * reference_dy) > 0.04:
            continue

        lengths = sorted((item[2] for item in bar_vectors), reverse=True)
        if not (
            0.72 <= lengths[1] / longest <= 0.78
            and 0.47 <= lengths[2] / longest <= 0.53
        ):
            continue
        bar_centers = [
            ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            for start, end in bars
        ]
        if (
            max(center[0] * reference_dx + center[1] * reference_dy for center in bar_centers)
            - min(center[0] * reference_dx + center[1] * reference_dy for center in bar_centers)
            > longest * 0.025
        ):
            continue

        longest_center = bar_centers[longest_index]
        attached = min(lead, key=lambda point: distance(point, longest_center))
        contact_end = max(lead, key=lambda point: distance(point, longest_center))
        if distance(attached, longest_center) > longest * 0.025:
            continue
        if distance(contact_end, contact_center) > longest * 0.025:
            continue

        outward_dx = (contact_end[0] - attached[0]) / lead_length
        outward_dy = (contact_end[1] - attached[1]) / lead_length
        stepped = sorted(
            (
                -(
                    (center[0] - attached[0]) * outward_dx
                    + (center[1] - attached[1]) * outward_dy
                )
                / longest,
                bar_vectors[index][2] / longest,
            )
            for index, center in enumerate(bar_centers)
            if index != longest_index
        )
        if len(stepped) != 2 or not (
            0.23 <= stepped[0][0] <= 0.27
            and 0.48 <= stepped[1][0] <= 0.52
            and 0.72 <= stepped[0][1] <= 0.78
            and 0.47 <= stepped[1][1] <= 0.53
        ):
            continue

        circle_axial = (
            (circle_center[0] - attached[0]) * outward_dx
            + (circle_center[1] - attached[1]) * outward_dy
        ) / longest
        circle_lateral = abs(
            (circle_center[0] - attached[0]) * outward_dy
            - (circle_center[1] - attached[1]) * outward_dx
        ) / longest
        if not (
            0.72 <= lead_length / longest <= 0.78
            and 0.12 <= contact_radius / longest <= 0.15
            and 0.84 <= circle_radius / longest <= 0.91
            and 0.10 <= circle_axial <= 0.15
            and circle_lateral <= 0.02
        ):
            continue

        if any(
            distance(point, circle_center) > circle_radius * 1.01
            for segment in segments
            for point in segment
        ):
            continue
        if distance(contact_center, circle_center) + contact_radius > circle_radius * 1.02:
            continue
        return True
    return False


def _has_ground_symbol_topology(shape: Mapping[str, Any]) -> bool:
    """Bind the round contact, orthogonal lead, and three ground bars."""

    try:
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 4 or len(contacts) != 1:
        return False

    def vector(segment: tuple[tuple[float, float], tuple[float, float]]) -> tuple[float, float, float]:
        (sx, sy), (ex, ey) = segment
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        return dx / length, dy / length, length

    def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    contact_center, contact_radius = contacts[0]
    for lead_index, lead in enumerate(segments):
        bars = [item for index, item in enumerate(segments) if index != lead_index]
        try:
            lead_dx, lead_dy, lead_length = vector(lead)
            bar_vectors = [vector(item) for item in bars]
        except ZeroDivisionError:
            continue
        reference_dx, reference_dy, _ = bar_vectors[0]
        if any(
            abs(reference_dx * dy - reference_dy * dx) > 0.05
            for dx, dy, _ in bar_vectors[1:]
        ):
            continue
        if abs(lead_dx * reference_dx + lead_dy * reference_dy) > 0.1:
            continue

        bar_centers = [
            ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            for start, end in bars
        ]
        lead_start, lead_end = lead
        if any(
            abs((center[0] - lead_start[0]) * lead_dy - (center[1] - lead_start[1]) * lead_dx)
            > 0.06
            for center in bar_centers
        ):
            continue

        longest_index = max(range(3), key=lambda index: bar_vectors[index][2])
        longest_center = bar_centers[longest_index]
        attached, contact_end = sorted(
            (lead_start, lead_end), key=lambda point: distance(point, longest_center)
        )
        if distance(attached, longest_center) > 0.06:
            continue
        if distance(contact_end, contact_center) > max(0.04, contact_radius * 0.35):
            continue

        ladder = sorted(
            (
                distance(center, attached),
                bar_vectors[index][2],
            )
            for index, center in enumerate(bar_centers)
        )
        distances = [item[0] for item in ladder]
        lengths = [item[1] for item in ladder]
        if (
            distances[0] <= 0.06
            and distances[1] - distances[0] >= 0.04
            and distances[2] - distances[1] >= 0.04
            and lengths[0] > lengths[1] * 1.05
            and lengths[1] > lengths[2] * 1.05
            and lengths[2] / lengths[0] >= 0.35
            and lead_length / lengths[2] >= 1.0
        ):
            return True
    return False


def _is_high_confidence_external_multi_port_geometry(
    shape: Mapping[str, Any],
    *,
    port_count: int,
    width: float,
    height: float,
) -> bool:
    """Recognize the rotation/scale invariant 2x2 KK2P topology."""

    if _is_kk2p_four_port_geometry(shape, port_count=port_count, width=width, height=height):
        return True

    try:
        radii = [float(value) for value in shape.get("arc_radii") or []]
        primitive_count = int(shape.get("primitive_count", 0))
    except (TypeError, ValueError):
        return False
    if port_count not in {4, 5, 6} or len(radii) not in {2, 3}:
        return False
    if any(radius <= 0.0 for radius in radii):
        return False
    mean_radius = sum(radii) / len(radii)
    if max(radii) - min(radii) > mean_radius * 0.05:
        return False
    normalized_size = max(width, height) / mean_radius
    aspect = max(width, height) / min(width, height) if min(width, height) > 0 else 0.0
    return primitive_count >= 24 and 12.0 <= normalized_size <= 22.0 and 1.0 <= aspect <= 2.0


def _has_fjl_line_bound_two_port_topology(
    shape: Mapping[str, Any], *, port_count: int
) -> bool:
    """Match FJL/Mirror; the two line-bound inner contacts are ports."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    labels = {str(value).strip() for value in shape.get("text_values") or []}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    lines = shape.get("normalized_line_segments") or []
    if not (
        port_count == 2
        and {key: int(h.get(key, 0)) for key in ("CIRCLE", "LINE", "LWPOLYLINE", "TEXT")}
        == {"CIRCLE": 2, "LINE": 2, "LWPOLYLINE": 4, "TEXT": 2}
        and sum(int(h.get(key, 0)) for key in ("ARC", "HATCH", "INSERT")) == 0
        and labels == {"1", "2"}
        and len(contacts) == 4
        and len(circles) == 2
        and len(lines) == 2
        and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 4
        and 5.45 <= float(shape.get("oriented_aspect_ratio") or 0.0) <= 5.75
    ):
        return False
    try:
        contact_rows = [
            (tuple(map(float, item["center"][:2])), float(item.get("chord_radius", item["radius"])))
            for item in contacts
        ]
        circle_rows = [
            (tuple(map(float, item["center"][:2])), float(item["radius"])) for item in circles
        ]
        radii = [item[1] for item in contact_rows]
        radius = sum(radii) / len(radii)
        if radius <= 0 or max(radii) / min(radii) > 1.04:
            return False
        if any(not 4.9 <= item[1] / radius <= 5.1 for item in circle_rows):
            return False
        first, last = max(combinations([item[0] for item in contact_rows], 2), key=lambda pair: math.dist(*pair))
        span = math.dist(first, last)
        axis = ((last[0] - first[0]) / span, (last[1] - first[1]) / span)
        normal = (-axis[1], axis[0])
        projections = sorted((point[0] - first[0]) * axis[0] + (point[1] - first[1]) * axis[1] for point, _ in contact_rows)
        offsets = [abs((point[0] - first[0]) * normal[0] + (point[1] - first[1]) * normal[1]) for point, _ in contact_rows]
        if max(offsets) > radius * .08:
            return False
        contact_gaps = [(right - left) / radius for left, right in zip(projections, projections[1:])]
        if not (7.8 <= contact_gaps[0] <= 8.2 and 39.5 <= contact_gaps[1] <= 40.5 and 7.8 <= contact_gaps[2] <= 8.2):
            return False
        circle_projections = sorted((point[0] - first[0]) * axis[0] + (point[1] - first[1]) * axis[1] for point, _ in circle_rows)
        if not 29.5 <= (circle_projections[1] - circle_projections[0]) / radius <= 30.5:
            return False
        lengths = [math.dist(row["start"], row["end"]) / radius for row in lines]
        return len(lengths) == 2 and all(29.5 <= value <= 30.5 for value in lengths)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _kk_of_main_port_count(shape: Mapping[str, Any]) -> int | None:
    """Return 2/4/6 only for a complete KK main grid plus isolated OF area."""
    h = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    labels = {str(value).strip() for value in shape.get("text_values") or []}
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    circles = shape.get("normalized_circles") or []
    for main_count, line_count in ((2, 18), (4, 22), (6, 28)):
        required_labels = {str(index) for index in range(1, main_count + 1)} | {"11", "12", "14"}
        if not (
            labels == required_labels
            and {key: int(h.get(key, 0)) for key in ("CIRCLE", "LINE", "LWPOLYLINE", "TEXT")}
            == {"CIRCLE": 3, "LINE": line_count, "LWPOLYLINE": main_count + 3, "TEXT": main_count + 3}
            and sum(int(h.get(key, 0)) for key in ("ARC", "HATCH", "INSERT")) == 0
            and len(contacts) == main_count + 3
            and len(circles) == 3
            and int(shape.get("closed_bulged_lwpolyline_count", 0)) == main_count + 3
            and 1.05 <= float(shape.get("oriented_aspect_ratio") or 0.0) <= 1.30
        ):
            continue
        try:
            contact_rows = [
                (tuple(map(float, item["center"][:2])), float(item.get("chord_radius", item["radius"])), item)
                for item in contacts
            ]
            circle_rows = [
                (tuple(map(float, item["center"][:2])), float(item["radius"])) for item in circles
            ]
            contact_radii = [item[1] for item in contact_rows]
            circle_radii = [item[1] for item in circle_rows]
            if min(contact_radii + circle_radii) <= 0 or max(contact_radii) / min(contact_radii) > 1.04 or max(circle_radii) / min(circle_radii) > 1.04:
                continue
            if not 3.9 <= (sum(circle_radii) / 3) / (sum(contact_radii) / len(contact_radii)) <= 4.1:
                continue
            aux_indices = []
            aux_vectors = []
            for center, circle_radius in circle_rows:
                index = min(range(len(contact_rows)), key=lambda candidate: math.dist(center, contact_rows[candidate][0]))
                if index in aux_indices:
                    break
                vector = (contact_rows[index][0][0] - center[0], contact_rows[index][0][1] - center[1])
                distance = math.hypot(*vector)
                if not 2.4 <= distance / circle_radius <= 2.6:
                    break
                aux_indices.append(index)
                aux_vectors.append((vector[0] / distance, vector[1] / distance))
            if len(aux_indices) != 3 or any(abs(first[0] * second[1] - first[1] * second[0]) > .03 for first, second in combinations(aux_vectors, 2)):
                continue
            main_contacts = [item[2] for index, item in enumerate(contact_rows) if index not in aux_indices]
            main_points = [tuple(map(float, item["center"][:2])) for item in main_contacts]
            grid_extent = max(
                max(point[0] for point in main_points) - min(point[0] for point in main_points),
                max(point[1] for point in main_points) - min(point[1] for point in main_points),
            )
            if _is_rotation_invariant_contact_grid(
                main_contacts,
                columns=main_count // 2,
                rows=2,
                tolerance=grid_extent * .19,
            ):
                return main_count
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            continue
    return None


def _is_kk2p_four_port_geometry(
    shape: Mapping[str, Any], *, port_count: int, width: float, height: float
) -> bool:
    """Match KK2P by measured topology, never by name or fingerprint."""
    if port_count != 4 or width <= 0 or height <= 0:
        return False
    aspect = max(width, height) / min(width, height)
    hist = shape.get("entity_histogram") or shape.get("primitive_histogram") or {}
    count = lambda key: int(hist.get(key, 0) or 0)
    if not (count("LINE") == 9 and count("LWPOLYLINE") == 4 and count("TEXT") == 4):
        return False
    if not (1.0 <= aspect <= 1.45 and int(shape.get("closed_bulged_lwpolyline_count", 0)) == 4):
        return False
    values = {str(v).strip() for v in (shape.get("text_values") or shape.get("normalized_text_values") or [])}
    if values != {"1", "2", "3", "4"}:
        return False
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    if len(contacts) != 4:
        return False
    centers = [c.get("center", c) for c in contacts if isinstance(c, Mapping)]
    if len(centers) != 4:
        return False
    try:
        contact_points = [(float(point[0]), float(point[1])) for point in centers]
    except (IndexError, TypeError, ValueError):
        return False
    distances = sorted(
        math.hypot(
            contact_points[left][0] - contact_points[right][0],
            contact_points[left][1] - contact_points[right][1],
        )
        for left in range(4)
        for right in range(left + 1, 4)
    )
    tolerance = max(distances[-1] * 0.08, 1e-6)
    if not (
        distances[0] > 0.0
        and abs(distances[0] - distances[1]) <= tolerance
        and abs(distances[2] - distances[3]) <= tolerance
        and abs(distances[4] - distances[5]) <= tolerance
        and distances[4] > distances[2] * 1.05
    ):
        return False
    # Extractor emits this explicit invariant; requiring it prevents ordinary
    # four-contact drawings with the same entity counts from being absorbed.
    return bool(shape.get("kk2p_2x2_topology"))


def _cluster_projection_counts(values: Sequence[float], *, tolerance: float = 0.16) -> list[int]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and abs(value - sum(groups[-1]) / len(groups[-1])) <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return sorted(len(group) for group in groups)


def _is_rotation_invariant_contact_grid(
    contacts: Sequence[Any], *, columns: int, rows: int, tolerance: float = 0.16
) -> bool:
    try:
        points = [
            (
                float((item.get("center", item))[0]),
                float((item.get("center", item))[1]),
            )
            for item in contacts
            if isinstance(item, Mapping)
        ]
    except (IndexError, TypeError, ValueError):
        return False
    if len(points) != columns * rows:
        return False
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    covariance_xx = sum((point[0] - cx) ** 2 for point in points) / len(points)
    covariance_yy = sum((point[1] - cy) ** 2 for point in points) / len(points)
    covariance_xy = sum(
        (point[0] - cx) * (point[1] - cy) for point in points
    ) / len(points)
    angle = 0.5 * math.atan2(
        2.0 * covariance_xy, covariance_xx - covariance_yy
    )
    axes = (
        (math.cos(angle), math.sin(angle)),
        (-math.sin(angle), math.cos(angle)),
    )
    projection_counts = []
    for axis_x, axis_y in axes:
        projection_counts.append(
            _cluster_projection_counts(
                [point[0] * axis_x + point[1] * axis_y for point in points],
                tolerance=tolerance,
            )
        )
    expected_columns = sorted([rows] * columns)
    expected_rows = sorted([columns] * rows)
    return (
        projection_counts[0] == expected_columns
        and projection_counts[1] == expected_rows
    ) or (
        projection_counts[1] == expected_columns
        and projection_counts[0] == expected_rows
    )


def _has_repeated_three_row_coil_panel_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize the 2x6 semicircle grid, spine, and duplicated contacts."""

    try:
        arcs = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
                float(item["sweep_deg"]),
            )
            for item in shape.get("normalized_arcs") or []
        ]
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(arcs) != 12 or len(segments) != 26 or len(contacts) != 4:
        return False
    arc_radius = sum(item[1] for item in arcs) / len(arcs)
    if arc_radius <= 1e-9 or any(
        abs(radius - arc_radius) > arc_radius * 0.04
        or abs(sweep - 180.0) > 1.0
        for _, radius, sweep in arcs
    ):
        return False

    vectors = []
    for start, end in segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        vectors.append((dx / length, dy / length, length, start, end))
    best_group: list[int] = []
    for index, item in enumerate(vectors):
        group = [
            other
            for other, candidate in enumerate(vectors)
            if abs(item[0] * candidate[1] - item[1] * candidate[0]) <= 0.04
        ]
        if len(group) > len(best_group):
            best_group = group
    if len(best_group) != 25:
        return False
    axis_x, axis_y = vectors[best_group[0]][0], vectors[best_group[0]][1]
    normal_x, normal_y = -axis_y, axis_x
    perpendicular = [index for index in range(26) if index not in best_group]
    if len(perpendicular) != 1:
        return False
    spine = vectors[perpendicular[0]]
    if abs(spine[0] * axis_x + spine[1] * axis_y) > 0.04:
        return False

    origin = arcs[0][0]

    def project(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        return dx * axis_x + dy * axis_y, dx * normal_x + dy * normal_y

    def clusters(values: list[float], tolerance: float) -> list[list[float]]:
        result: list[list[float]] = []
        for value in sorted(values):
            if result and abs(value - sum(result[-1]) / len(result[-1])) <= tolerance:
                result[-1].append(value)
            else:
                result.append([value])
        return result

    arc_axis = clusters([project(center)[0] for center, _, _ in arcs], arc_radius * 0.08)
    arc_normal = clusters([project(center)[1] for center, _, _ in arcs], arc_radius * 0.08)
    if not (
        len(arc_axis) == 2
        and all(len(group) == 6 for group in arc_axis)
        and len(arc_normal) == 6
        and all(len(group) == 2 for group in arc_normal)
    ):
        return False
    axis_centers = [sum(group) / len(group) for group in arc_axis]
    normal_centers = [sum(group) / len(group) for group in arc_normal]
    if not (2.60 <= (axis_centers[1] - axis_centers[0]) / arc_radius <= 2.74):
        return False
    normal_gaps = [
        (normal_centers[index + 1] - normal_centers[index]) / arc_radius
        for index in range(5)
    ]
    if any(
        abs(value - expected) > 0.08
        for value, expected in zip(normal_gaps, (2.0, 10.0 / 3.0, 2.0, 10.0 / 3.0, 2.0))
    ):
        return False

    contact_radius = sum(radius for _, radius in contacts) / len(contacts)
    if not (0.12 <= contact_radius / arc_radius <= 0.15):
        return False
    contact_axis = clusters(
        [project(center)[0] for center, _ in contacts], arc_radius * 0.08
    )
    contact_normal = clusters(
        [project(center)[1] for center, _ in contacts], arc_radius * 0.08
    )
    if not (
        len(contact_axis) == 1
        and len(contact_axis[0]) == 4
        and len(contact_normal) == 2
        and all(len(group) == 2 for group in contact_normal)
    ):
        return False
    contact_axis_value = sum(contact_axis[0]) / len(contact_axis[0])
    contact_normal_values = [sum(group) / len(group) for group in contact_normal]
    if not (
        3.9
        <= min(abs(contact_axis_value - value) for value in axis_centers) / arc_radius
        <= 4.1
        and 5.25
        <= (contact_normal_values[1] - contact_normal_values[0]) / arc_radius
        <= 5.42
    ):
        return False
    spine_axis = sum(project(point)[0] for point in (spine[3], spine[4])) / 2.0
    spine_normals = sorted(project(point)[1] for point in (spine[3], spine[4]))
    return (
        abs(spine_axis - contact_axis_value) <= arc_radius * 0.08
        and spine_normals[0] <= contact_normal_values[0] + arc_radius * 0.08
        and spine_normals[1] >= contact_normal_values[1] - arc_radius * 0.08
        and 11.8 <= spine[2] / arc_radius <= 12.2
    )


def _has_dual_row_hatched_signal_panel_topology(shape: Mapping[str, Any]) -> bool:
    """Recognize two repeated hatched rows whose visible extrema are not ports."""

    try:
        circles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item["radius"]),
            )
            for item in shape.get("normalized_circles") or []
        ]
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
        rectangles = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                sorted(float(value) for value in item["edge_lengths"]),
            )
            for item in shape.get("normalized_closed_straight_lwpolylines") or []
        ]
        contacts = [
            (
                (float(item["center"][0]), float(item["center"][1])),
                float(item.get("chord_radius", item["radius"])),
            )
            for item in shape.get("normalized_closed_bulged_contacts") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if not (
        len(circles) == 2
        and len(segments) == 10
        and len(rectangles) == 4
        and len(contacts) == 2
    ):
        return False
    circle_radius = sum(radius for _, radius in circles) / 2.0
    if circle_radius <= 1e-9 or any(
        abs(radius - circle_radius) > circle_radius * 0.03
        for _, radius in circles
    ):
        return False
    row_dx = circles[1][0][0] - circles[0][0][0]
    row_dy = circles[1][0][1] - circles[0][0][1]
    row_spacing = math.hypot(row_dx, row_dy)
    if not 5.9 <= row_spacing / circle_radius <= 6.1:
        return False
    row_x, row_y = row_dx / row_spacing, row_dy / row_spacing
    axis_x, axis_y = -row_y, row_x

    def project(
        point: tuple[float, float], origin: tuple[float, float]
    ) -> tuple[float, float]:
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        return (
            (dx * axis_x + dy * axis_y) / circle_radius,
            (dx * row_x + dy * row_y) / circle_radius,
        )

    parsed_segments = []
    for start, end in segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        parsed_segments.append(
            (
                length,
                (dx / length, dy / length),
                start,
                end,
                ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
            )
        )
    ordered_segments = sorted(parsed_segments, key=lambda item: item[0])
    short_segments, long_segments = ordered_segments[:8], ordered_segments[8:]
    if any(
        not 30.8 <= item[0] / circle_radius <= 31.2
        or abs(item[1][0] * axis_y - item[1][1] * axis_x) > 0.02
        for item in long_segments
    ):
        return False
    unmatched_circles = {0, 1}
    for segment in long_segments:
        nearest = min(
            unmatched_circles,
            key=lambda index: math.hypot(
                segment[4][0] - circles[index][0][0],
                segment[4][1] - circles[index][0][1],
            ),
        )
        if math.hypot(
            segment[4][0] - circles[nearest][0][0],
            segment[4][1] - circles[nearest][0][1],
        ) > circle_radius * 0.04:
            return False
        unmatched_circles.remove(nearest)

    row_segments: list[list[tuple[Any, ...]]] = [[], []]
    for segment in short_segments:
        distances = [abs(project(segment[4], center)[1]) for center, _ in circles]
        row_index = 0 if distances[0] <= distances[1] else 1
        if distances[row_index] > 0.6 or abs(project(segment[4], circles[row_index][0])[0]) > 0.75:
            return False
        row_segments[row_index].append(segment)
    if any(len(group) != 4 for group in row_segments):
        return False

    def row_descriptors(
        group: list[tuple[Any, ...]], origin: tuple[float, float]
    ) -> list[tuple[float, float, float, float]]:
        result = []
        for _, _, start, end, _ in group:
            left, right = sorted((project(start, origin), project(end, origin)))
            result.append((left[0], left[1], right[0], right[1]))
        return sorted(result)

    left_descriptors = row_descriptors(row_segments[0], circles[0][0])
    right_descriptors = row_descriptors(row_segments[1], circles[1][0])
    if any(
        abs(left - right) > 0.04
        for left_row, right_row in zip(left_descriptors, right_descriptors)
        for left, right in zip(left_row, right_row)
    ):
        return False
    expected_short_lengths = (0.825, 0.825, 1.8, 1.8)
    for group in row_segments:
        ratios = sorted(item[0] / circle_radius for item in group)
        if any(
            abs(value - expected) > 0.04
            for value, expected in zip(ratios, expected_short_lengths)
        ):
            return False

    rectangle_rows: list[list[float]] = [[], []]
    for center, edge_lengths in rectangles:
        if len(edge_lengths) != 4 or any(
            abs(value / circle_radius - expected) > 0.04
            for value, expected in zip(edge_lengths, (0.8, 0.8, 2.0, 2.0))
        ):
            return False
        distances = [abs(project(center, circle)[1]) for circle, _ in circles]
        row_index = 0 if distances[0] <= distances[1] else 1
        if distances[row_index] > 0.06:
            return False
        rectangle_rows[row_index].append(project(center, circles[row_index][0])[0])
    if any(len(group) != 2 for group in rectangle_rows):
        return False
    for group in rectangle_rows:
        offsets = sorted(group)
        if not (
            -14.7 <= offsets[0] <= -14.3
            and 14.3 <= offsets[1] <= 14.7
        ):
            return False

    contact_radius = sum(radius for _, radius in contacts) / 2.0
    if not 0.38 <= contact_radius / circle_radius <= 0.42 or any(
        abs(radius - contact_radius) > contact_radius * 0.04
        for _, radius in contacts
    ):
        return False
    host_candidates = [
        index
        for index, (circle, _) in enumerate(circles)
        if all(abs(project(center, circle)[1]) <= 0.06 for center, _ in contacts)
    ]
    if len(host_candidates) != 1:
        return False
    host = circles[host_candidates[0]][0]
    offsets = sorted(project(center, host)[0] for center, _ in contacts)
    return (
        -25.0 <= offsets[0] <= -23.0
        and 23.0 <= offsets[1] <= 25.0
        and 47.8 <= offsets[1] - offsets[0] <= 48.2
        and abs((offsets[0] + offsets[1]) / 2.0) <= 0.6
    )


def _has_four_coil_topology(shape: Mapping[str, Any]) -> bool:
    arcs = shape.get("normalized_arcs") or []
    if len(arcs) != 4 or not _is_rotation_invariant_contact_grid(
        arcs, columns=2, rows=2, tolerance=0.08
    ):
        return False
    try:
        if any(abs(float(arc.get("sweep_deg", 0.0)) - 180.0) > 2.0 for arc in arcs):
            return False
        segments = [
            (
                (float(item["start"][0]), float(item["start"][1])),
                (float(item["end"][0]), float(item["end"][1])),
            )
            for item in shape.get("normalized_line_segments") or []
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if len(segments) != 10:
        return False
    directions: list[tuple[float, float]] = []
    for start, end in segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return False
        directions.append((dx / length, dy / length))
    for reference in directions:
        parallel = [
            direction
            for direction in directions
            if abs(reference[0] * direction[1] - reference[1] * direction[0]) <= 0.05
        ]
        if len(parallel) != 9:
            continue
        remaining = next(direction for direction in directions if direction not in parallel)
        if abs(reference[0] * remaining[0] + reference[1] * remaining[1]) <= 0.1:
            return True
    return False


def _is_kk3p_six_port_geometry(
    shape: Mapping[str, Any], *, port_count: int, width: float, height: float
) -> bool:
    """Recognize a numbered 3x2 six-contact body without using its block name."""

    if port_count != 6 or width <= 0.0 or height <= 0.0:
        return False
    histogram = shape.get("entity_histogram") or {}
    try:
        line_count = int(histogram.get("LINE", 0))
        polyline_count = int(histogram.get("LWPOLYLINE", 0))
        text_count = int(histogram.get("TEXT", 0))
        closed_contacts = int(shape.get("closed_bulged_lwpolyline_count", 0))
    except (TypeError, ValueError):
        return False
    aspect = max(width, height) / min(width, height)
    values = {
        str(value).strip() for value in shape.get("text_values") or []
    }
    contacts = shape.get("normalized_closed_bulged_contacts") or []
    return (
        line_count == 16
        and polyline_count == 6
        and text_count == 6
        and closed_contacts == 6
        and values == {"1", "2", "3", "4", "5", "6"}
        and 1.0 <= aspect <= 1.15
        and _is_rotation_invariant_contact_grid(contacts, columns=3, rows=2)
    )


def evaluate_symbol_behavior(
    family: Mapping[str, Any],
    *,
    reviewed_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert family evidence into fail-closed behavior flags."""

    family_id = str(family.get("family_id") or "")
    reviewed_mode = str((reviewed_policy or {}).get("mode") or "")
    exact_ignore = reviewed_mode == "IGNORE_ELECTRICAL"
    exact_table_container = reviewed_mode == "TABLE_CONTAINER_NO_DIRECT_PORTS"
    exact_wire_primitive = reviewed_mode == "WIRE_PRIMITIVE"
    geometry_ignore = bool(
        family_id in GEOMETRY_IGNORE_FAMILIES
        and family.get("classifier_status") == "MATCHED"
        and str(family.get("family_evidence_source") or "").startswith(
            "MACHINE_GEOMETRY_RULE"
        )
    )
    ignore = exact_ignore or geometry_ignore
    table_container = bool(
        exact_table_container
        or (
            family_id in TABLE_CONTAINER_FAMILIES
            and family.get("classifier_status") == "MATCHED"
            and str(family.get("family_evidence_source") or "").startswith(
                "MACHINE_GEOMETRY_RULE"
            )
        )
    )
    geometry_wire_primitive = bool(
        family_id in WIRE_PRIMITIVE_FAMILIES
        and family.get("classifier_status") == "MATCHED"
        and str(family.get("family_evidence_source") or "").startswith(
            "MACHINE_GEOMETRY_RULE"
        )
    )
    wire_primitive = exact_wire_primitive or geometry_wire_primitive
    external_only = family_id.startswith("component.external_")
    terminal = family_id.startswith("labelled_terminal.")
    behavior_mode = (
        "IGNORE"
        if ignore
        else "WIRE_PRIMITIVE"
        if wire_primitive
        else "TABLE_CONTAINER"
        if table_container
        else "TERMINAL_NO_INTERNAL"
        if terminal
        else "EXTERNAL_PORTS_ONLY"
        if external_only
        else "REVIEW_ONLY"
    )
    allow_ports = bool(
        (terminal or external_only)
        and not ignore
        and not table_container
        and not wire_primitive
    )
    return {
        "behavior_policy_version": BEHAVIOR_POLICY_VERSION,
        "behavior_mode": behavior_mode,
        "allow_port_emission": allow_ports,
        "allow_external_attachment": allow_ports,
        "allow_internal_connectivity": False,
        "allow_electrical_union": False,
        "allow_critical_issue": False,
        "suppressed_by_policy": ignore or table_container or wire_primitive,
        "table_mapping_preserved": table_container,
        "decision_reason_codes": [
            "HUMAN_EXACT_IGNORE_POLICY"
            if exact_ignore
            else "HUMAN_EXACT_WIRE_PRIMITIVE_POLICY"
            if exact_wire_primitive
            else "HUMAN_EXACT_TABLE_CONTAINER_POLICY"
            if exact_table_container
            else "GEOMETRY_TABLE_CONTAINER_MATCH"
            if table_container
            else "GEOMETRY_WIRE_PRIMITIVE_MATCH"
            if geometry_wire_primitive
            else "GEOMETRY_IGNORE_FAMILY_MATCH"
            if geometry_ignore
            else "FAMILY_EXTERNAL_ONLY_NO_INTERNAL"
            if external_only
            else "FAMILY_TERMINAL_NO_INTERNAL"
            if terminal
            else "MACHINE_FAMILY_REVIEW_ONLY"
        ],
        "authority": "SHADOW_ONLY",
    }


@dataclass(frozen=True, slots=True)
class ProposedPort:
    port_id: str
    local_position: tuple[float, float, float]
    outward_direction: tuple[float, float, float]
    port_type: str
    confidence: float
    evidence_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    notes: str | None = None
    logical_port_identity: str | None = None
    component_group: str | None = None
    component_pin: str | None = None
    attachment_side: str | None = None

    def to_review_port(self) -> dict[str, Any]:
        value = {
            "port_id": self.port_id,
            "local_position": list(self.local_position),
            "outward_direction": list(self.outward_direction),
            "port_type": self.port_type,
            "aliases": [],
            "source_ids": list(self.source_ids),
            "annotation_status": "MACHINE_PROPOSED",
        }
        for key in (
            "logical_port_identity",
            "component_group",
            "component_pin",
            "attachment_side",
        ):
            item = getattr(self, key)
            if item is not None:
                value[key] = item
        return value

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["local_position"] = list(self.local_position)
        value["outward_direction"] = list(self.outward_direction)
        value["evidence_codes"] = list(self.evidence_codes)
        value["source_ids"] = list(self.source_ids)
        return value


@dataclass(frozen=True, slots=True)
class SymbolPortProposal:
    definition_name: str
    definition_fingerprint: str | None
    source_dxf: str | None
    ports: tuple[ProposedPort, ...]
    method: str
    status: str
    notes: tuple[str, ...] = ()
    geometry_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "definition_name": self.definition_name,
            "definition_fingerprint": self.definition_fingerprint,
            "source_dxf": self.source_dxf,
            "method": self.method,
            "status": self.status,
            "notes": list(self.notes),
            "geometry_summary": self.geometry_summary or {},
            "ports": [port.to_dict() for port in self.ports],
        }


def _round_point(point: tuple[float, float], digits: int = 4) -> tuple[float, float]:
    return (round(float(point[0]), digits), round(float(point[1]), digits))


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-18:
        return _distance(point, start)
    projection = max(
        0.0,
        min(
            1.0,
            ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
            / length_squared,
        ),
    )
    return _distance(
        point,
        (start[0] + projection * dx, start[1] + projection * dy),
    )


def _normalize(vector: tuple[float, float]) -> tuple[float, float, float]:
    x, y = vector
    norm = math.hypot(x, y)
    if norm <= 1e-12:
        return (1.0, 0.0, 0.0)
    return (x / norm, y / norm, 0.0)


def _cluster_points(
    points: Sequence[tuple[float, float]],
    *,
    eps: float = 0.15,
) -> list[tuple[float, float]]:
    clusters: list[list[tuple[float, float]]] = []
    for point in points:
        placed = False
        for cluster in clusters:
            cx = sum(item[0] for item in cluster) / len(cluster)
            cy = sum(item[1] for item in cluster) / len(cluster)
            if _distance(point, (cx, cy)) <= eps:
                cluster.append(point)
                placed = True
                break
        if not placed:
            clusters.append([point])
    centroids: list[tuple[float, float]] = []
    for cluster in clusters:
        centroids.append(
            (
                sum(item[0] for item in cluster) / len(cluster),
                sum(item[1] for item in cluster) / len(cluster),
            )
        )
    return centroids


def extract_block_segments(block: Any) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], dict[str, int]]:
    """Return wire-like segments and entity-type counts from a block layout."""

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    counts: Counter[str] = Counter()
    try:
        entities = list(block)
    except Exception:
        return [], {}
    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
        except Exception:
            continue
        counts[entity_type] += 1
        try:
            if entity_type == "LINE":
                start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
                segments.append((start, end))
            elif entity_type == "LWPOLYLINE":
                points = [
                    (float(point[0]), float(point[1]))
                    for point in entity.get_points("xy")
                ]
                for left, right in zip(points, points[1:]):
                    segments.append((left, right))
                if len(points) > 1 and bool(getattr(entity, "closed", False)):
                    segments.append((points[-1], points[0]))
            elif entity_type == "POLYLINE":
                points = []
                for vertex in entity.vertices:
                    try:
                        location = vertex.dxf.location
                        points.append((float(location.x), float(location.y)))
                    except Exception:
                        continue
                for left, right in zip(points, points[1:]):
                    segments.append((left, right))
                if len(points) > 1 and bool(getattr(entity, "is_closed", False)):
                    segments.append((points[-1], points[0]))
            elif entity_type == "ARC":
                center = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                radius = float(entity.dxf.radius)
                start_angle = math.radians(float(entity.dxf.start_angle))
                end_angle = math.radians(float(entity.dxf.end_angle))
                start = (
                    center[0] + radius * math.cos(start_angle),
                    center[1] + radius * math.sin(start_angle),
                )
                end = (
                    center[0] + radius * math.cos(end_angle),
                    center[1] + radius * math.sin(end_angle),
                )
                segments.append((start, end))
            elif entity_type == "CIRCLE":
                # Circles alone do not create wire ports; skip.
                continue
        except Exception:
            continue
    return segments, dict(sorted(counts.items()))


def extract_block_shape_features(block: Any) -> dict[str, Any]:
    """Extract name-independent local geometry features for safe classification."""

    try:
        entities = list(block)
    except Exception:
        return {
            "arc_radii": [],
            "circle_radii": [],
            "primitive_count": 0,
            "primitive_histogram": {},
            "entity_histogram": {},
            "text_count": 0,
            "width": 0.0,
            "height": 0.0,
        }

    points: list[tuple[float, float]] = []
    arc_radii: list[float] = []
    arc_descriptors: list[tuple[float, float, float, float, float, float]] = []
    circle_radii: list[float] = []
    circle_descriptors: list[tuple[float, float, float]] = []
    primitive_count = 0
    primitive_histogram: Counter[str] = Counter()
    entity_histogram: Counter[str] = Counter()
    text_count = 0
    text_values: list[str] = []
    line_lengths: list[float] = []
    line_directions: list[tuple[float, float]] = []
    parallel_line_lengths: list[float] = []
    line_segments: list[tuple[float, float, float, float]] = []
    open_lwpolyline_segments: list[tuple[float, float, float, float]] = []
    open_lwpolyline_descriptors: list[
        tuple[tuple[tuple[float, float, float, float, float], ...], bool]
    ] = []
    closed_bulged_contacts: list[tuple[float, float, float, float, bool]] = []
    closed_straight_lwpolylines: list[
        tuple[
            float,
            float,
            float,
            float,
            tuple[float, ...],
            tuple[tuple[float, float], ...],
        ]
    ] = []
    closed_bulged_lwpolyline_count = 0
    insert_descriptors: list[
        tuple[float, float, float, float, float, dict[str, int]]
    ] = []
    primitive_types = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE"}
    text_types = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}

    def add_point(x: Any, y: Any) -> None:
        try:
            px = float(x)
            py = float(y)
        except (TypeError, ValueError):
            return
        if math.isfinite(px) and math.isfinite(py):
            points.append((px, py))

    def angle_on_arc(angle: float, start: float, end: float) -> bool:
        sweep = (end - start) % 360.0
        offset = (angle - start) % 360.0
        return offset <= sweep + 1e-9

    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
        except Exception:
            continue
        entity_histogram[entity_type] += 1
        if entity_type in text_types:
            text_count += 1
            try:
                value = str(entity.dxf.text).strip()
                if value:
                    text_values.append(value)
            except Exception:
                pass
        if entity_type == "INSERT":
            try:
                insert = entity.dxf.insert
                child = entity.doc.blocks.get(str(entity.dxf.name))
                child_histogram = Counter(
                    str(child_entity.dxftype() or "").upper()
                    for child_entity in child
                )
                insert_descriptors.append(
                    (
                        float(insert.x),
                        float(insert.y),
                        float(getattr(entity.dxf, "rotation", 0.0) or 0.0) % 360.0,
                        float(getattr(entity.dxf, "xscale", 1.0) or 1.0),
                        float(getattr(entity.dxf, "yscale", 1.0) or 1.0),
                        dict(sorted(child_histogram.items())),
                    )
                )
            except Exception:
                pass
        if entity_type not in primitive_types:
            continue
        primitive_count += 1
        primitive_histogram[entity_type] += 1
        try:
            if entity_type == "LINE":
                sx, sy = float(entity.dxf.start.x), float(entity.dxf.start.y)
                ex, ey = float(entity.dxf.end.x), float(entity.dxf.end.y)
                add_point(sx, sy)
                add_point(ex, ey)
                length = math.hypot(ex - sx, ey - sy)
                if length > 1e-9:
                    line_lengths.append(length)
                    line_directions.append(((ex - sx) / length, (ey - sy) / length))
                    line_segments.append((sx, sy, ex, ey))
            elif entity_type == "LWPOLYLINE":
                polyline_points = list(entity.get_points("xy"))
                polyline_vertex_data = [
                    (
                        float(point[0]),
                        float(point[1]),
                        float(point[2]),
                        float(point[3]),
                        float(point[4]),
                    )
                    for point in entity.get_points("xyseb")
                ]
                invisible = bool(int(getattr(entity.dxf, "invisible", 0) or 0))
                for point in polyline_points:
                    add_point(point[0], point[1])
                is_closed = bool(getattr(entity, "closed", False))
                if is_closed:
                    bulged = False
                    try:
                        bulged = any(abs(float(point[2])) > 1e-9 for point in entity.get_points("xyb"))
                    except Exception:
                        pass
                    if bulged:
                        closed_bulged_lwpolyline_count += 1
                        if polyline_points:
                            xs = [float(point[0]) for point in polyline_points]
                            ys = [float(point[1]) for point in polyline_points]
                            chord_diameter = max(
                                (
                                    math.hypot(
                                        float(right[0]) - float(left[0]),
                                        float(right[1]) - float(left[1]),
                                    )
                                    for left_index, left in enumerate(polyline_points)
                                    for right in polyline_points[left_index + 1 :]
                                ),
                                default=0.0,
                            )
                            bbox_diameter = max(
                                max(xs) - min(xs), max(ys) - min(ys)
                            )
                            closed_bulged_contacts.append(
                                (
                                    (min(xs) + max(xs)) / 2.0,
                                    (min(ys) + max(ys)) / 2.0,
                                    bbox_diameter / 2.0,
                                    chord_diameter / 2.0,
                                    invisible,
                                )
                            )
                    elif polyline_points:
                        xs = [float(point[0]) for point in polyline_points]
                        ys = [float(point[1]) for point in polyline_points]
                        edge_lengths = tuple(
                            math.hypot(
                                float(right[0]) - float(left[0]),
                                float(right[1]) - float(left[1]),
                            )
                            for left, right in zip(
                                polyline_points,
                                polyline_points[1:] + polyline_points[:1],
                            )
                        )
                        closed_straight_lwpolylines.append(
                            (
                                (min(xs) + max(xs)) / 2.0,
                                (min(ys) + max(ys)) / 2.0,
                                max(xs) - min(xs),
                                max(ys) - min(ys),
                                edge_lengths,
                                tuple(
                                    (float(point[0]), float(point[1]))
                                    for point in polyline_points
                                ),
                            )
                        )
                elif len(polyline_points) >= 2:
                    open_lwpolyline_descriptors.append(
                        (tuple(polyline_vertex_data), invisible)
                    )
                    try:
                        has_bulge = any(
                            abs(float(point[2])) > 1e-9
                            for point in entity.get_points("xyb")
                        )
                    except Exception:
                        has_bulge = True
                    if not has_bulge:
                        for start, end in zip(polyline_points, polyline_points[1:]):
                            sx, sy = float(start[0]), float(start[1])
                            ex, ey = float(end[0]), float(end[1])
                            if math.hypot(ex - sx, ey - sy) > 1e-9:
                                open_lwpolyline_segments.append((sx, sy, ex, ey))
            elif entity_type == "POLYLINE":
                for vertex in entity.vertices:
                    location = vertex.dxf.location
                    add_point(location.x, location.y)
            elif entity_type == "ARC":
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                radius = float(entity.dxf.radius)
                start = float(entity.dxf.start_angle) % 360.0
                end = float(entity.dxf.end_angle) % 360.0
                if radius > 0.0 and math.isfinite(radius):
                    arc_radii.append(radius)
                    sweep = (end - start) % 360.0
                    midpoint_angle = math.radians((start + sweep / 2.0) % 360.0)
                    arc_descriptors.append(
                        (
                            cx,
                            cy,
                            radius,
                            sweep,
                            cx + radius * math.cos(midpoint_angle),
                            cy + radius * math.sin(midpoint_angle),
                        )
                    )
                    for angle in (start, end, 0.0, 90.0, 180.0, 270.0):
                        if angle in (start, end) or angle_on_arc(angle, start, end):
                            radians = math.radians(angle)
                            add_point(
                                cx + radius * math.cos(radians),
                                cy + radius * math.sin(radians),
                            )
            elif entity_type == "CIRCLE":
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                radius = float(entity.dxf.radius)
                if radius > 0.0 and math.isfinite(radius):
                    circle_radii.append(radius)
                    circle_descriptors.append((cx, cy, radius))
                    add_point(cx - radius, cy)
                    add_point(cx + radius, cy)
                    add_point(cx, cy - radius)
                    add_point(cx, cy + radius)
        except Exception:
            continue

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
    else:
        width = 0.0
        height = 0.0
    # Parallelism uses the absolute cross product, hence is invariant under
    # rotation and reflection.  Store the lengths of the largest parallel
    # group so the three bar levels can be checked without entity ordering.
    parallel_group: list[float] = []
    parallel_direction: tuple[float, float] | None = None
    for index, direction in enumerate(line_directions):
        group = [line_lengths[index]]
        for other, other_direction in enumerate(line_directions):
            if other != index and abs(direction[0] * other_direction[1] - direction[1] * other_direction[0]) <= 0.05:
                group.append(line_lengths[other])
        if len(group) > len(parallel_group):
            parallel_group = group
            parallel_direction = direction
    oriented_width = width
    oriented_height = height
    if points and parallel_direction is not None:
        axis_x, axis_y = parallel_direction
        normal_x, normal_y = -axis_y, axis_x
        axis_values = [point[0] * axis_x + point[1] * axis_y for point in points]
        normal_values = [point[0] * normal_x + point[1] * normal_y for point in points]
        oriented_width = max(axis_values) - min(axis_values)
        oriented_height = max(normal_values) - min(normal_values)
    scale = max(line_lengths) if line_lengths else 0.0
    coordinate_scale = max(width, height, scale)
    normalized_segments = []
    normalized_open_lwpolyline_segments = []
    normalized_open_lwpolylines = []
    normalized_contacts = []
    normalized_arcs = []
    normalized_circles = []
    normalized_straight_polylines = []
    normalized_inserts = []
    if coordinate_scale > 1e-9 and points:
        origin_x = min(point[0] for point in points)
        origin_y = min(point[1] for point in points)
        normalized_segments = [
            {
                "start": [
                    round((sx - origin_x) / coordinate_scale, 6),
                    round((sy - origin_y) / coordinate_scale, 6),
                ],
                "end": [
                    round((ex - origin_x) / coordinate_scale, 6),
                    round((ey - origin_y) / coordinate_scale, 6),
                ],
            }
            for sx, sy, ex, ey in line_segments
        ]
        normalized_open_lwpolyline_segments = [
            {
                "start": [
                    round((sx - origin_x) / coordinate_scale, 6),
                    round((sy - origin_y) / coordinate_scale, 6),
                ],
                "end": [
                    round((ex - origin_x) / coordinate_scale, 6),
                    round((ey - origin_y) / coordinate_scale, 6),
                ],
            }
            for sx, sy, ex, ey in open_lwpolyline_segments
        ]
        normalized_open_lwpolylines = [
            {
                "invisible": invisible,
                "vertices": [
                    {
                        "point": [
                            round((x - origin_x) / coordinate_scale, 6),
                            round((y - origin_y) / coordinate_scale, 6),
                        ],
                        "start_width": round(start_width / coordinate_scale, 6),
                        "end_width": round(end_width / coordinate_scale, 6),
                        "bulge": round(bulge, 9),
                    }
                    for x, y, start_width, end_width, bulge in vertices
                ],
            }
            for vertices, invisible in open_lwpolyline_descriptors
        ]
        normalized_contacts = [
            {
                "center": [
                    round((cx - origin_x) / coordinate_scale, 6),
                    round((cy - origin_y) / coordinate_scale, 6),
                ],
                "radius": round(radius / coordinate_scale, 6),
                "chord_radius": round(chord_radius / coordinate_scale, 6),
                "invisible": invisible,
            }
            for cx, cy, radius, chord_radius, invisible in closed_bulged_contacts
        ]
        normalized_arcs = [
            {
                "center": [
                    round((cx - origin_x) / coordinate_scale, 6),
                    round((cy - origin_y) / coordinate_scale, 6),
                ],
                "radius": round(radius / coordinate_scale, 6),
                "sweep_deg": round(sweep, 6),
                "midpoint": [
                    round((midpoint_x - origin_x) / coordinate_scale, 6),
                    round((midpoint_y - origin_y) / coordinate_scale, 6),
                ],
            }
            for cx, cy, radius, sweep, midpoint_x, midpoint_y in arc_descriptors
        ]
        normalized_circles = [
            {
                "center": [
                    round((cx - origin_x) / coordinate_scale, 6),
                    round((cy - origin_y) / coordinate_scale, 6),
                ],
                "radius": round(radius / coordinate_scale, 6),
            }
            for cx, cy, radius in circle_descriptors
        ]
        normalized_straight_polylines = [
            {
                "center": [
                    round((cx - origin_x) / coordinate_scale, 6),
                    round((cy - origin_y) / coordinate_scale, 6),
                ],
                "width": round(polyline_width / coordinate_scale, 6),
                "height": round(polyline_height / coordinate_scale, 6),
                "edge_lengths": [
                    round(length / coordinate_scale, 6)
                    for length in edge_lengths
                ],
                "vertices": [
                    [
                        round((x - origin_x) / coordinate_scale, 6),
                        round((y - origin_y) / coordinate_scale, 6),
                    ]
                    for x, y in vertices
                ],
            }
            for (
                cx,
                cy,
                polyline_width,
                polyline_height,
                edge_lengths,
                vertices,
            ) in closed_straight_lwpolylines
        ]
        normalized_inserts = [
            {
                "center": [
                    round((x - origin_x) / coordinate_scale, 6),
                    round((y - origin_y) / coordinate_scale, 6),
                ],
                "rotation_deg": round(rotation, 6),
                "xscale": round(xscale, 6),
                "yscale": round(yscale, 6),
                "child_entity_histogram": child_histogram,
            }
            for x, y, rotation, xscale, yscale, child_histogram in insert_descriptors
        ]
    outer_box_topology = any(
        float(item.get("width", 0.0)) >= 0.65
        and float(item.get("height", 0.0)) >= 0.65
        for item in normalized_straight_polylines
    )
    length_clusters: list[list[float]] = []
    normalized_lengths = sorted(
        (length / scale for length in line_lengths), reverse=False
    ) if scale else []
    for value in normalized_lengths:
        for cluster in length_clusters:
            if abs(value - sum(cluster) / len(cluster)) <= 0.015:
                cluster.append(value)
                break
        else:
            length_clusters.append([value])
    short_cluster_counts = [
        len(cluster)
        for cluster in length_clusters
        if sum(cluster) / len(cluster) <= 0.45
    ]
    boxed_diode_repeated_topology = bool(
        outer_box_topology
        and len(line_segments) == 13
        and len(normalized_contacts) == 2
        and any(count >= 4 for count in short_cluster_counts)
        and sum(count >= 2 for count in short_cluster_counts) >= 3
    )
    # The explicit flag is deliberately derived from geometry only.  It is
    # intentionally conservative: callers can also provide this evidence from
    # an upstream extractor when entity ordering/arc tessellation is unavailable.
    kk2p_topology = False
    if len(line_segments) == 9 and len(normalized_contacts) == 4 and text_count == 4:
        directions: list[tuple[float, float]] = []
        lengths = []
        for sx, sy, ex, ey in line_segments:
            length = math.hypot(ex - sx, ey - sy)
            if length > 1e-9:
                directions.append(((ex - sx) / length, (ey - sy) / length))
                lengths.append(length / max(line_lengths))
        if len(directions) == 9:
            reference = directions[0]
            first_indices = [
                index
                for index, direction in enumerate(directions)
                if abs(reference[0] * direction[1] - reference[1] * direction[0])
                <= 0.05
            ]
            second_indices = [
                index for index in range(len(directions)) if index not in first_indices
            ]
            if first_indices and second_indices:
                second_reference = directions[second_indices[0]]
                second_parallel = all(
                    abs(
                        second_reference[0] * directions[index][1]
                        - second_reference[1] * directions[index][0]
                    )
                    <= 0.05
                    for index in second_indices
                )
                perpendicular = abs(
                    reference[0] * second_reference[0]
                    + reference[1] * second_reference[1]
                ) <= 0.1
                kk2p_topology = (
                    sorted((len(first_indices), len(second_indices))) == [4, 5]
                    and second_parallel
                    and perpendicular
                    and len({round(value, 2) for value in lengths}) >= 3
                )
    return {
        "arc_radii": sorted(round(radius, 6) for radius in arc_radii),
        "circle_radii": sorted(round(radius, 6) for radius in circle_radii),
        "primitive_count": primitive_count,
        "primitive_histogram": dict(sorted(primitive_histogram.items())),
        "entity_histogram": dict(sorted(entity_histogram.items())),
        "text_count": text_count,
        "text_values": text_values,
        "width": round(width, 6),
        "height": round(height, 6),
        "oriented_width": round(oriented_width, 6),
        "oriented_height": round(oriented_height, 6),
        "oriented_aspect_ratio": round(
            max(oriented_width, oriented_height) / min(oriented_width, oriented_height),
            6,
        ) if min(oriented_width, oriented_height) > 1e-9 else 0.0,
        "normalized_line_lengths": [round(value / scale, 6) for value in line_lengths] if scale else [],
        "parallel_line_group_max": len(parallel_group),
        "normalized_parallel_line_lengths": [round(value / scale, 6) for value in parallel_group] if scale else [],
        "closed_bulged_lwpolyline_count": closed_bulged_lwpolyline_count,
        "normalized_line_segments": normalized_segments,
        "normalized_open_lwpolyline_segments": normalized_open_lwpolyline_segments,
        "normalized_open_lwpolylines": normalized_open_lwpolylines,
        "normalized_closed_bulged_contacts": normalized_contacts,
        "normalized_arcs": normalized_arcs,
        "normalized_circles": normalized_circles,
        "normalized_closed_straight_lwpolylines": normalized_straight_polylines,
        "normalized_inserts": normalized_inserts,
        "outer_box_topology": outer_box_topology,
        "repeated_diode_count": 2 if boxed_diode_repeated_topology else 0,
        "boxed_diode_repeated_topology": boxed_diode_repeated_topology,
        "kk2p_2x2_topology": kk2p_topology,
    }


def propose_ports_from_segments(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    *,
    source_id: str,
    max_ports: int = 4,
    cluster_eps: float = 0.2,
) -> tuple[list[ProposedPort], dict[str, Any], tuple[str, ...]]:
    """Propose electrical ports from free endpoints of wire-like geometry."""

    notes: list[str] = []
    if not segments:
        return [], {"segment_count": 0}, ("NO_SEGMENTS",)

    endpoint_hits: list[tuple[float, float]] = []
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)
    for start, end in segments:
        s = _round_point(start)
        e = _round_point(end)
        endpoint_hits.append(s)
        endpoint_hits.append(e)
        if s != e:
            adjacency[s].append(e)
            adjacency[e].append(s)

    degree = Counter(endpoint_hits)
    free_points = [point for point, count in degree.items() if count == 1]
    if not free_points:
        # Fall back to geometric extremes of all endpoints.
        free_points = list(degree.keys())
        notes.append("No degree-1 free endpoints; using geometric extremes.")

    clustered = _cluster_points(free_points, eps=cluster_eps)
    if not clustered:
        return [], {"segment_count": len(segments)}, ("NO_CLUSTERED_POINTS",)

    xs = [point[0] for point in clustered]
    ys = [point[1] for point in clustered]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    horizontal = width >= height

    def extremity_score(point: tuple[float, float]) -> float:
        if horizontal:
            return abs(point[0] - cx) + 0.15 * abs(point[1] - cy)
        return abs(point[1] - cy) + 0.15 * abs(point[0] - cx)

    ranked = sorted(clustered, key=extremity_score, reverse=True)

    # Repeated full-width rows are a stronger multi-port signal than raw bbox
    # aspect. This excludes decorative/mechanical free ends inside the symbol.
    selected: list[tuple[float, float]] = []
    paired_row_points: set[tuple[float, float]] = set()
    selected_complete_rows = False
    row_groups: list[list[tuple[float, float]]] = []
    for point in sorted(clustered, key=lambda item: (item[1], item[0])):
        for group in row_groups:
            mean_y = sum(item[1] for item in group) / len(group)
            if abs(point[1] - mean_y) <= cluster_eps:
                group.append(point)
                break
        else:
            row_groups.append([point])
    full_width_rows: list[tuple[float, tuple[float, float], tuple[float, float]]] = []
    if horizontal and width > 1e-6:
        edge_tolerance = max(cluster_eps * 2.0, width * 0.05)
        for group in row_groups:
            left = min(group, key=lambda item: item[0])
            right = max(group, key=lambda item: item[0])
            if (
                right[0] - left[0] >= width * 0.8
                and left[0] <= min_x + edge_tolerance
                and right[0] >= max_x - edge_tolerance
            ):
                full_width_rows.append(
                    (sum(item[1] for item in group) / len(group), left, right)
                )
    if max_ports >= 4 and len(full_width_rows) >= 2:
        for _, left, right in sorted(full_width_rows, key=lambda item: item[0]):
            for point in (left, right):
                if len(selected) >= max_ports:
                    break
                if all(_distance(point, existing) > cluster_eps for existing in selected):
                    selected.append(point)
                    paired_row_points.add(point)
            if len(selected) >= max_ports:
                break
        notes.append(
            "Selected paired full-width row endpoints for repeated multi-port geometry."
        )
        selected_complete_rows = True
    elif horizontal and width > 1e-6:
        left = min(clustered, key=lambda point: (point[0], abs(point[1] - cy)))
        right = max(clustered, key=lambda point: (point[0], -abs(point[1] - cy)))
        selected = [left, right]
        notes.append("Selected left/right extremes for horizontal schematic symbol.")
    elif height > 1e-6:
        bottom = min(clustered, key=lambda point: (point[1], abs(point[0] - cx)))
        top = max(clustered, key=lambda point: (point[1], -abs(point[0] - cx)))
        selected = [bottom, top]
        notes.append("Selected bottom/top extremes for vertical schematic symbol.")
    else:
        selected = ranked[: max(1, min(max_ports, 2))]
        notes.append("Degenerate bbox; selected ranked free endpoints.")

    # Only expand beyond 2 ports when free endpoints form a clearly 2D terminal
    # pattern (near-square spread). Elongated series symbols stay 2-port.
    aspect = (
        max(width, height) / min(width, height)
        if min(width, height) > 1e-6
        else 999.0
    )
    multi_terminal = max_ports > 2 and aspect <= 1.6
    if selected_complete_rows or len(selected) >= max_ports:
        pass
    elif multi_terminal:
        axis_extremes = [
            min(clustered, key=lambda point: (point[0], point[1])),
            max(clustered, key=lambda point: (point[0], -point[1])),
            min(clustered, key=lambda point: (point[1], point[0])),
            max(clustered, key=lambda point: (point[1], -point[0])),
        ]
        for point in axis_extremes:
            if len(selected) >= max_ports:
                break
            if all(_distance(point, existing) > cluster_eps for existing in selected):
                selected.append(point)
        notes.append("Expanded to multi-terminal extremes due to near-square free-end spread.")
    elif max_ports > 2:
        notes.append("Kept 2-port principal-axis proposal for elongated schematic symbol.")




    ports: list[ProposedPort] = []
    for index, point in enumerate(selected, start=1):
        # Outward direction: away from centroid; refine using attached neighbor if any.
        rounded = _round_point(point)
        neighbors = adjacency.get(rounded) or []
        if neighbors:
            # Average neighbor vector, then invert for outward.
            nx = sum(neighbor[0] - point[0] for neighbor in neighbors) / len(neighbors)
            ny = sum(neighbor[1] - point[1] for neighbor in neighbors) / len(neighbors)
            outward = _normalize((-nx, -ny))
            evidence = ("FREE_ENDPOINT", "OUTWARD_FROM_ATTACHED_SEGMENT")
        else:
            outward = _normalize((point[0] - cx, point[1] - cy))
            evidence = ("GEOMETRIC_EXTREME", "OUTWARD_FROM_CENTROID")
        if point in paired_row_points:
            evidence = (*evidence, "REPEATED_FULL_WIDTH_ROW_PORT")
        confidence = 0.55 if "FREE_ENDPOINT" in evidence else 0.4
        if len(selected) == 2:
            confidence += 0.15
        if "REPEATED_FULL_WIDTH_ROW_PORT" in evidence:
            confidence += 0.15
        ports.append(
            ProposedPort(
                port_id=f"MP{index}",
                local_position=(float(point[0]), float(point[1]), 0.0),
                outward_direction=outward,
                port_type="ELECTRICAL",
                confidence=min(confidence, 0.85),
                evidence_codes=evidence,
                source_ids=(source_id,),
                notes="Machine geometry proposal; requires human confirmation.",
            )
        )

    summary = {
        "segment_count": len(segments),
        "unique_endpoint_count": len(degree),
        "free_endpoint_count": len(free_points),
        "clustered_candidate_count": len(clustered),
        "bbox": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": width,
            "height": height,
        },
        "principal_axis": "horizontal" if horizontal else "vertical",
        "centroid": {"x": cx, "y": cy},
        "selected_port_count": len(ports),
    }
    return ports, summary, tuple(notes)


_COMMUNICATION_PANEL_GROUP_PATTERN = re.compile(r"^(?P<kind>COM|CAN|LAN)(?P<number>\d+)$", re.IGNORECASE)
_COMMUNICATION_PANEL_EXTERNAL_ENDPOINT_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)*[A-Za-z]{1,6}\d*(?:-\d+)*|[A-Za-z]{1,6}\d+(?:-\d+)*)$",
    re.IGNORECASE,
)


def _clean_communication_panel_endpoint(value: Any) -> str:
    return str(value or "").strip().strip("&@").strip()


def _is_communication_panel_external_endpoint(value: Any) -> bool:
    cleaned = _clean_communication_panel_endpoint(value)
    return bool(
        cleaned
        and not cleaned.isdigit()
        and _COMMUNICATION_PANEL_GROUP_PATTERN.fullmatch(cleaned) is None
        and _COMMUNICATION_PANEL_EXTERNAL_ENDPOINT_PATTERN.fullmatch(cleaned)
    )


def _propose_three_contact_socket_ports(
    block: Any, *, source_id: str
) -> list[ProposedPort]:
    """Emit the three radial outer contacts of a socket-like component."""

    circles: list[tuple[tuple[float, float], float, str]] = []
    contacts: list[tuple[tuple[float, float], float, str]] = []
    texts: list[tuple[str, tuple[float, float]]] = []
    try:
        entities = list(block)
    except Exception:
        return []
    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
            handle = str(entity.dxf.handle or "")
            if entity_type == "CIRCLE":
                center = entity.dxf.center
                circles.append(
                    ((float(center.x), float(center.y)), float(entity.dxf.radius), handle)
                )
            elif entity_type == "LWPOLYLINE" and bool(getattr(entity, "closed", False)):
                points = list(entity.get_points("xyb"))
                if not points or not any(abs(float(point[2])) > 1e-9 for point in points):
                    continue
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
                contacts.append(
                    (
                        ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0),
                        max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0,
                        handle,
                    )
                )
            elif entity_type in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                raw = (
                    entity.plain_text()
                    if hasattr(entity, "plain_text")
                    else entity.dxf.text
                )
                position = entity.dxf.insert
                value = str(raw or "").strip().upper()
                if value:
                    texts.append((value, (float(position.x), float(position.y))))
        except Exception:
            continue

    selected_contacts: list[tuple[str, tuple[float, float], str]] = []
    body_center: tuple[float, float] | None = None
    body_handle = ""
    if len(circles) == 4 and len(contacts) == 6:
        outer_center, outer_radius, outer_handle = max(
            circles, key=lambda item: item[1]
        )
        if outer_radius <= 1e-9:
            return []
        outer_contacts = [
            item
            for item in contacts
            if 1.45
            <= math.hypot(
                item[0][0] - outer_center[0], item[0][1] - outer_center[1]
            )
            / outer_radius
            <= 1.55
        ]
        if len(outer_contacts) != 3:
            return []
        body_center = outer_center
        body_handle = outer_handle
        selected_contacts = [
            (f"P{index}", center, handle)
            for index, (center, _, handle) in enumerate(
                sorted(
                    outer_contacts,
                    key=lambda item: math.atan2(
                        item[0][1] - outer_center[1],
                        item[0][0] - outer_center[0],
                    ),
                ),
                start=1,
            )
        ]
    elif len(circles) == 3 and {"E", "L", "N"}.issubset(
        {value for value, _ in texts}
    ) and len(contacts) >= 4:
        minimum_contact_radius = min(radius for _, radius, _ in contacts)
        if minimum_contact_radius <= 1e-9:
            return []
        small_contacts = [
            item
            for item in contacts
            if item[1] <= minimum_contact_radius * 1.1
        ]
        outline_contacts = [
            item
            for item in contacts
            if item[1] >= minimum_contact_radius * 10.0
        ]
        if not (4 <= len(small_contacts) <= 6 and len(outline_contacts) == 1):
            return []
        body_center = outline_contacts[0][0]
        body_handle = outline_contacts[0][2]
        used_circle_handles: set[str] = set()
        used_contact_handles: set[str] = set()
        for pin in ("E", "L", "N"):
            label_position = next(position for value, position in texts if value == pin)
            circle = min(
                circles,
                key=lambda item: math.hypot(
                    item[0][0] - label_position[0],
                    item[0][1] - label_position[1],
                ),
            )
            contact = min(
                small_contacts,
                key=lambda item: math.hypot(
                    item[0][0] - circle[0][0],
                    item[0][1] - circle[0][1],
                ),
            )
            if circle[2] in used_circle_handles or contact[2] in used_contact_handles:
                return []
            used_circle_handles.add(circle[2])
            used_contact_handles.add(contact[2])
            selected_contacts.append((pin, contact[0], contact[2]))
    else:
        return []

    if body_center is None or len(selected_contacts) != 3:
        return []
    ports: list[ProposedPort] = []
    for pin, center, handle in selected_contacts:
        dx = center[0] - body_center[0]
        dy = center[1] - body_center[1]
        norm = math.hypot(dx, dy)
        if norm <= 1e-9:
            return []
        ports.append(
            ProposedPort(
                port_id=f"SOCKET:{pin}",
                local_position=(center[0], center[1], 0.0),
                outward_direction=(dx / norm, dy / norm, 0.0),
                port_type="ELECTRICAL",
                confidence=0.98,
                evidence_codes=(
                    "THREE_RADIAL_OUTER_CONTACTS",
                    "OUTER_SOCKET_CIRCLE",
                    "NO_INTERNAL_CONNECTIVITY",
                ),
                source_ids=(source_id, f"body:{body_handle}", f"contact:{handle}"),
                notes="Three-contact socket draft; bind E/L/N from instance text and never union ports.",
                attachment_side="radial",
            )
        )
    return ports


def _propose_communication_panel_ports(
    block: Any, *, source_id: str
) -> tuple[list[ProposedPort], dict[str, Any]]:
    """Extract repeated labelled COM/CAN cells without using block identity."""

    try:
        entities = list(block)
    except Exception:
        return [], {}

    texts: list[dict[str, Any]] = []
    rectangles: list[dict[str, Any]] = []
    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
        except Exception:
            continue
        if entity_type in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            try:
                raw = (
                    entity.plain_text()
                    if hasattr(entity, "plain_text")
                    else entity.dxf.text
                )
                position = entity.dxf.insert
                value = str(raw or "").strip()
                if value:
                    texts.append(
                        {
                            "value": value,
                            "x": float(position.x),
                            "y": float(position.y),
                            "handle": str(entity.dxf.handle or ""),
                        }
                    )
            except Exception:
                continue
        elif entity_type == "LWPOLYLINE" and bool(getattr(entity, "closed", False)):
            try:
                points = list(entity.get_points("xyb"))
                if len(points) != 4 or any(abs(float(point[2])) > 1e-9 for point in points):
                    continue
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
                unique_x = sorted({round(value, 6) for value in xs})
                unique_y = sorted({round(value, 6) for value in ys})
                if len(unique_x) != 2 or len(unique_y) != 2:
                    continue
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                if width <= 1e-9 or height <= 1e-9:
                    continue
                rectangles.append(
                    {
                        "min_x": min(xs),
                        "max_x": max(xs),
                        "min_y": min(ys),
                        "max_y": max(ys),
                        "center_x": (min(xs) + max(xs)) / 2.0,
                        "center_y": (min(ys) + max(ys)) / 2.0,
                        "width": width,
                        "height": height,
                        "handle": str(entity.dxf.handle or ""),
                    }
                )
            except Exception:
                continue

    square_candidates = [
        item
        for item in rectangles
        if 0.9 <= item["width"] / item["height"] <= 1.1
    ]
    size_counts = Counter(
        (round(item["width"], 4), round(item["height"], 4))
        for item in square_candidates
    )
    if not size_counts:
        return [], {}
    dominant_size, _ = size_counts.most_common(1)[0]
    cells = [
        item
        for item in square_candidates
        if (round(item["width"], 4), round(item["height"], 4)) == dominant_size
    ]
    cell_width, cell_height = dominant_size

    labelled_cells: list[tuple[dict[str, Any], str, str]] = []
    for cell in cells:
        labels = [
            item
            for item in texts
            if str(item["value"]).isdigit()
            and cell["min_x"] - cell_width * 0.05
            <= float(item["x"])
            <= cell["max_x"] + cell_width * 0.05
            and cell["min_y"] - cell_height * 0.05
            <= float(item["y"])
            <= cell["max_y"] + cell_height * 0.05
        ]
        if len(labels) == 1 and labels[0]["value"] in {"1", "2", "3", "4", "5"}:
            labelled_cells.append((cell, str(labels[0]["value"]), str(labels[0]["handle"])))

    groups: list[tuple[dict[str, Any], re.Match[str]]] = []
    group_counts: Counter[str] = Counter()
    for item in texts:
        match = _COMMUNICATION_PANEL_GROUP_PATTERN.fullmatch(str(item["value"]))
        if match is None:
            continue
        groups.append((item, match))
        group_counts[match.group("kind").upper()] += 1

    mapping_groups = [
        (item, match)
        for item, match in groups
        if match.group("kind").upper() in {"COM", "CAN"}
    ]
    row_values: list[float] = []
    for item, _ in sorted(mapping_groups, key=lambda value: float(value[0]["y"])):
        y = float(item["y"])
        if not row_values or abs(y - row_values[-1]) > cell_height * 0.6:
            row_values.append(y)
        else:
            row_values[-1] = (row_values[-1] + y) / 2.0
    row_count = len(row_values)
    row_midpoint = sum(row_values) / len(row_values) if row_values else 0.0

    ports: list[ProposedPort] = []
    used_cells: set[str] = set()
    for group, match in sorted(
        mapping_groups,
        key=lambda value: (-float(value[0]["y"]), float(value[0]["x"])),
    ):
        kind = match.group("kind").upper()
        group_name = f"{kind}{match.group('number')}"
        expected = 5 if kind == "COM" else 3
        candidates = [
            (cell, pin, text_handle)
            for cell, pin, text_handle in labelled_cells
            if str(cell["handle"]) not in used_cells
            and abs(float(cell["center_y"]) - float(group["y"]))
            <= cell_height * 0.65
            and float(cell["center_x"]) > float(group["x"])
            and float(cell["center_x"]) - float(group["x"])
            <= cell_width * (expected + 1.25)
        ]
        candidates = sorted(candidates, key=lambda value: float(value[0]["center_x"]))[:expected]
        if len(candidates) != expected or {pin for _, pin, _ in candidates} != {
            str(number) for number in range(1, expected + 1)
        }:
            continue
        top_side = float(group["y"]) > row_midpoint
        attachment_side = "top" if top_side else "bottom"
        outward = (0.0, 1.0, 0.0) if top_side else (0.0, -1.0, 0.0)
        for cell, pin, text_handle in candidates:
            used_cells.add(str(cell["handle"]))
            local_y = float(cell["max_y"] if top_side else cell["min_y"])
            logical_identity = f"{group_name}-{pin}"
            ports.append(
                ProposedPort(
                    port_id=f"PANEL:{group_name}:{pin}:OUT",
                    local_position=(float(cell["center_x"]), local_y, 0.0),
                    outward_direction=outward,
                    port_type="COMMUNICATION",
                    confidence=0.98,
                    evidence_codes=(
                        "REPEATED_CLOSED_SQUARE_CELL",
                        "NATIVE_GROUP_AND_PIN_LABEL",
                        "OUTWARD_CELL_SIDE",
                    ),
                    source_ids=(
                        source_id,
                        f"cell:{cell['handle']}",
                        f"group:{group['handle']}",
                        f"pin-text:{text_handle}",
                    ),
                    notes="Communication panel pin cell; bind outward only, never union through the panel.",
                    logical_port_identity=logical_identity,
                    component_group=group_name,
                    component_pin=pin,
                    attachment_side=attachment_side,
                )
            )

    # LAN sockets are drawn as one larger labelled rectangle per logical
    # connector.  Their tiny inner rectangles are decoration, not pins.  A
    # socket contributes one outward attachment locus; without an external
    # endpoint label the instance binder deliberately leaves it geometry-only.
    lan_socket_ports: list[ProposedPort] = []
    used_socket_handles: set[str] = set()
    lan_groups = [
        (item, match)
        for item, match in groups
        if match.group("kind").upper() == "LAN"
    ]
    for group, match in sorted(
        lan_groups,
        key=lambda value: (-float(value[0]["y"]), float(value[0]["x"])),
    ):
        containing = [
            rectangle
            for rectangle in rectangles
            if str(rectangle["handle"]) not in used_socket_handles
            and rectangle["min_x"] <= float(group["x"]) <= rectangle["max_x"]
            and rectangle["min_y"] <= float(group["y"]) <= rectangle["max_y"]
            and 1.8 * cell_width <= rectangle["width"] <= 3.2 * cell_width
            and 1.8 * cell_height <= rectangle["height"] <= 3.2 * cell_height
        ]
        if len(containing) != 1:
            continue
        socket = containing[0]
        top_side = float(group["y"]) > row_midpoint
        attachment_side = "top" if top_side else "bottom"
        outward = (0.0, 1.0, 0.0) if top_side else (0.0, -1.0, 0.0)
        local_y = float(socket["max_y"] if top_side else socket["min_y"])
        group_name = f"LAN{match.group('number')}"
        used_socket_handles.add(str(socket["handle"]))
        lan_socket_ports.append(
            ProposedPort(
                port_id=f"PANEL:{group_name}:OUT",
                local_position=(float(socket["center_x"]), local_y, 0.0),
                outward_direction=outward,
                port_type="COMMUNICATION",
                confidence=0.9,
                evidence_codes=(
                    "LABELLED_LAN_SOCKET_OUTLINE",
                    "OUTWARD_SOCKET_SIDE",
                ),
                source_ids=(
                    source_id,
                    f"socket:{socket['handle']}",
                    f"group:{group['handle']}",
                ),
                notes="Communication LAN socket attachment locus; no named external mapping without endpoint evidence.",
                logical_port_identity=group_name,
                component_group=group_name,
                attachment_side=attachment_side,
            )
        )

    mapped_cell_port_count = len(ports)
    ports.extend(lan_socket_ports)

    features = {
        "square_cell_count": len(cells),
        "labelled_cell_count": len(labelled_cells),
        "mapped_cell_port_count": mapped_cell_port_count,
        "lan_socket_port_count": len(lan_socket_ports),
        "row_count": row_count,
        "group_counts": dict(sorted(group_counts.items())),
        "dominant_cell_width": cell_width,
        "dominant_cell_height": cell_height,
        "dominant_cell_aspect": round(cell_width / cell_height, 6),
        "model": "repeated-labelled-communication-pin-cells-and-lan-sockets-v1",
    }
    return ports, features


def _propose_two_contact_mechanical_actuator_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Select only the two outer contacts of a PWF176-style mechanism."""

    contacts: list[tuple[tuple[float, float], float, str]] = []
    try:
        entities = list(block)
    except Exception:
        return ()
    for entity in entities:
        if str(entity.dxftype()).upper() != "LWPOLYLINE" or not bool(
            getattr(entity, "closed", False)
        ):
            continue
        try:
            points = list(entity.get_points("xyb"))
            if len(points) != 2 or not any(abs(float(point[2])) > 1e-9 for point in points):
                continue
            first = (float(points[0][0]), float(points[0][1]))
            second = (float(points[1][0]), float(points[1][1]))
            contacts.append(
                (
                    ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0),
                    math.hypot(second[0] - first[0], second[1] - first[1]) / 2.0,
                    str(getattr(entity.dxf, "handle", "") or ""),
                )
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return ()
    if len(contacts) != 2:
        return ()
    midpoint = (
        (contacts[0][0][0] + contacts[1][0][0]) / 2.0,
        (contacts[0][0][1] + contacts[1][0][1]) / 2.0,
    )
    ports = []
    for index, (center, _radius, handle) in enumerate(
        sorted(contacts, key=lambda item: (item[0][0], item[0][1])), start=1
    ):
        dx, dy = center[0] - midpoint[0], center[1] - midpoint[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return ()
        ports.append(
            ProposedPort(
                port_id=f"ACT{index}",
                local_position=(center[0], center[1], 0.0),
                outward_direction=(dx / length, dy / length, 0.0),
                port_type="ELECTRICAL",
                confidence=0.98,
                evidence_codes=(
                    "TWO_CONTACT_MECHANICAL_ACTUATOR",
                    "OUTER_ROUND_CONTACT",
                    "NO_INTERNAL_CONNECTIVITY",
                ),
                source_ids=tuple(value for value in (source_id, handle) if value),
                notes="Independent external contact; mechanical body never unions the two sides.",
                attachment_side="opposed_outer_side",
            )
        )
    return tuple(ports)


def _block_numeric_labels_and_round_contacts(
    block: Any,
) -> tuple[list[tuple[int, tuple[float, float]]], list[tuple[float, float]], list[tuple[tuple[float, float], float]]]:
    labels: list[tuple[int, tuple[float, float]]] = []
    contacts: list[tuple[float, float]] = []
    circles: list[tuple[tuple[float, float], float]] = []
    for entity in block:
        kind = str(entity.dxftype()).upper()
        try:
            if kind in {"TEXT", "ATTRIB", "ATTDEF"}:
                value = str(entity.dxf.text).strip()
                if re.fullmatch(r"[1-9][0-9]?", value):
                    insert = entity.dxf.insert
                    labels.append((int(value), (float(insert.x), float(insert.y))))
            elif kind == "CIRCLE":
                center = entity.dxf.center
                circles.append(((float(center.x), float(center.y)), float(entity.dxf.radius)))
            elif kind == "LWPOLYLINE" and bool(getattr(entity, "closed", False)):
                points = list(entity.get_points("xyb"))
                if points and any(abs(float(point[2])) > 1e-9 for point in points):
                    xs = [float(point[0]) for point in points]
                    ys = [float(point[1]) for point in points]
                    contacts.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
        except Exception:
            continue
    return labels, contacts, circles


def _propose_fjl_line_bound_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    labels, contacts, _ = _block_numeric_labels_and_round_contacts(block)
    main_labels = sorted((slot, point) for slot, point in labels if slot in {1, 2})
    if [slot for slot, _ in main_labels] != [1, 2] or len(contacts) != 4:
        return ()
    outer = max(combinations(contacts, 2), key=lambda pair: _distance(*pair))
    axis = _normalize((outer[1][0] - outer[0][0], outer[1][1] - outer[0][1]))
    ordered_contacts = sorted(
        contacts, key=lambda point: point[0] * axis[0] + point[1] * axis[1]
    )
    line_bound = (ordered_contacts[1], ordered_contacts[2])
    best = min(
        permutations(line_bound),
        key=lambda ordered: sum(_distance(label[1], contact) for label, contact in zip(main_labels, ordered)),
    )
    center = (
        sum(point[0] for point in contacts) / len(contacts),
        sum(point[1] for point in contacts) / len(contacts),
    )
    return tuple(
        ProposedPort(
            port_id=f"MP{slot}",
            local_position=(contact[0], contact[1], 0.0),
            outward_direction=_normalize((contact[0] - center[0], contact[1] - center[1])),
            port_type="ELECTRICAL",
            confidence=.99,
            evidence_codes=("FJL_LINE_BOUND_CONTACT", f"PORT_SLOT_{slot}"),
            source_ids=(source_id,),
            notes="FJL line-bound contact; pin 1/2 remains isolated and maps outward only.",
            component_pin=str(slot),
        )
        for (slot, _), contact in zip(main_labels, best)
    )


def _propose_kk_of_main_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    labels, contacts, circles = _block_numeric_labels_and_round_contacts(block)
    label_values = {slot for slot, _ in labels}
    if not {11, 12, 14} <= label_values or len(circles) != 3:
        return ()
    main_count = len(labels) - 3
    if main_count not in {2, 4, 6} or label_values != set(range(1, main_count + 1)) | {11, 12, 14} or len(contacts) != main_count + 3:
        return ()
    aux_indices = []
    for center, radius in circles:
        index = min(range(len(contacts)), key=lambda candidate: _distance(center, contacts[candidate]))
        if index in aux_indices or not 2.35 <= _distance(center, contacts[index]) / radius <= 2.65:
            return ()
        aux_indices.append(index)
    main_contacts = [point for index, point in enumerate(contacts) if index not in aux_indices]
    main_labels = sorted((slot, point) for slot, point in labels if 1 <= slot <= main_count)
    best_contacts: tuple[tuple[float, float], ...] | None = None
    best_score = math.inf
    for ordered in permutations(main_contacts):
        score = sum(_distance(label[1], contact) for label, contact in zip(main_labels, ordered))
        if score < best_score:
            best_score, best_contacts = score, ordered
    if best_contacts is None:
        return ()
    return tuple(
        ProposedPort(
            port_id=f"MP{slot}",
            local_position=(contact[0], contact[1], 0.0),
            outward_direction=_normalize((contact[0] - label_position[0], contact[1] - label_position[1])),
            port_type="ELECTRICAL",
            confidence=.99,
            evidence_codes=("KK_SELECTIVE_MAIN_CONTACT", f"PORT_SLOT_{slot}", "OF_AUXILIARY_SUPPRESSED"),
            source_ids=(source_id,),
            notes="KK main numbered contact; OF 11/12/14 is recognition-only and suppressed.",
            component_pin=str(slot),
        )
        for (slot, label_position), contact in zip(main_labels, best_contacts)
    )


def propose_ports_from_block(
    block: Any,
    *,
    definition_name: str,
    definition_fingerprint: str | None = None,
    source_dxf: str | Path | None = None,
    max_ports: int = 4,
) -> SymbolPortProposal:
    source_id = f"{SOURCE_KIND}:{definition_name}"
    name_key = definition_name.casefold()
    if any(token in name_key for token in ("title", "border", "frame", "图框", "标题")):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=(),
            method="free_endpoint_extremes_v1",
            status="SKIPPED_NON_ELECTRICAL",
            notes=("Definition name looks like title/border geometry; no electrical ports proposed.",),
            geometry_summary={"skip_reason": "title_or_border_name"},
        )
    segments, entity_counts = extract_block_segments(block)
    shape_features = extract_block_shape_features(block)
    wfs_ports = _propose_wfs_polarity_ports(block, source_id=source_id)
    if wfs_ports and _is_wfs_polarity_two_port_geometry(shape_features, port_count=len(wfs_ports)):
        return SymbolPortProposal(
            definition_name=definition_name, definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=wfs_ports, method="wfs_polarity_axial_ports_v1", status="PROPOSED",
            notes=("Selected only the two axial outer contacts; +/- circles are polarity marks and the terminals are isolated.",),
            geometry_summary={"entity_counts": entity_counts, "shape_features": shape_features,
                              "selected_port_count": 2, "principal_axis": "wfs_axial_contacts"},
        )
    fjl_ports = _propose_fjl_line_bound_ports(block, source_id=source_id)
    if fjl_ports and _has_fjl_line_bound_two_port_topology(
        shape_features, port_count=len(fjl_ports)
    ):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=fjl_ports,
            method="fjl_line_bound_contact_ports_v1",
            status="PROPOSED",
            notes=("Selected only FJL pins 1/2 at the two line-bound contacts; no body-internal union.",),
            geometry_summary={"entity_counts": entity_counts, "shape_features": shape_features,
                              "selected_port_count": 2, "principal_axis": "fjl_line_bound_contacts"},
        )
    kk_of_ports = _propose_kk_of_main_ports(block, source_id=source_id)
    if kk_of_ports and _kk_of_main_port_count(shape_features) == len(kk_of_ports):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=kk_of_ports,
            method="kk_of_selective_main_ports_v1",
            status="PROPOSED",
            notes=("Selected only KK main pins; OF 11/12/14 and mechanism geometry emit no ports.",),
            geometry_summary={"entity_counts": entity_counts, "shape_features": shape_features,
                              "selected_port_count": len(kk_of_ports), "principal_axis": "kk_main_contact_grid"},
        )
    actuator_ports = _propose_two_contact_mechanical_actuator_ports(
        block, source_id=source_id
    )
    if actuator_ports and _has_two_contact_mechanical_actuator_topology(
        shape_features, port_count=len(actuator_ports)
    ):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=actuator_ports,
            method="two_contact_mechanical_actuator_ports_v1",
            status="PROPOSED",
            notes=(
                "Selected the two opposed round contacts; open blade and lower actuator are non-conductive body geometry.",
            ),
            geometry_summary={
                "entity_counts": entity_counts,
                "shape_features": shape_features,
                "selected_port_count": len(actuator_ports),
                "principal_axis": "opposed_outer_contacts",
            },
        )
    socket_ports = _propose_three_contact_socket_ports(block, source_id=source_id)
    if socket_ports and _is_three_contact_socket_geometry(
        shape_features, port_count=len(socket_ports)
    ):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=tuple(socket_ports),
            method="three_contact_socket_ports_v1",
            status="PROPOSED",
            notes=(
                "Selected three independent radial socket contacts; bind E/L/N and the outer instance name at placement time.",
            ),
            geometry_summary={
                "entity_counts": entity_counts,
                "shape_features": shape_features,
                "selected_port_count": len(socket_ports),
                "principal_axis": "three_radial_contacts",
            },
        )
    panel_ports, panel_features = _propose_communication_panel_ports(
        block, source_id=source_id
    )
    if panel_features:
        shape_features["communication_panel_features"] = panel_features
    if panel_ports and _is_communication_multiport_panel_geometry(
        shape_features, port_count=len(panel_ports)
    ):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=tuple(panel_ports),
            method="repeated_communication_panel_ports_v1",
            status="PROPOSED",
            notes=(
                "Selected repeated labelled COM/CAN pin-cell and labelled LAN socket outward attachment loci; panel outline and LAN socket decoration excluded.",
            ),
            geometry_summary={
                "entity_counts": entity_counts,
                "shape_features": shape_features,
                "selected_port_count": len(panel_ports),
                "principal_axis": "cell_outward_sides",
            },
        )
    row_ports = _propose_single_row_contact_mechanism_port(
        block, source_id=source_id
    )
    if row_ports and _has_single_row_contact_mechanism_topology(
        shape_features, port_count=len(row_ports)
    ):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=tuple(row_ports),
            method="single_row_contact_mechanism_v1",
            status="PROPOSED",
            notes=(
                "Selected the single outward row contact; the circle and offset contact are mechanism geometry, not independent external ports.",
            ),
            geometry_summary={
                "entity_counts": entity_counts,
                "shape_features": shape_features,
                "selected_port_count": len(row_ports),
                "principal_axis": "single_row_external_side",
            },
        )
    ports, geometry_summary, notes = propose_ports_from_segments(
        segments,
        source_id=source_id,
        max_ports=max_ports,
    )
    horizontal_circle_box_ports = _propose_horizontal_numbered_two_circle_box_ports(
        block, source_id=source_id
    )
    horizontal_circle_box_applied = bool(
        horizontal_circle_box_ports
        and _has_horizontal_numbered_two_circle_box_topology(
            shape_features, port_count=len(horizontal_circle_box_ports)
        )
    )
    if horizontal_circle_box_applied:
        ports = list(horizontal_circle_box_ports)
        notes = (
            *notes,
            "Replaced outer-box corners with two independent circle-bound contacts.",
        )
        geometry_summary["selected_port_count"] = len(ports)
        geometry_summary["horizontal_two_circle_box_port_count"] = len(ports)
    vertical_box_ports = _propose_vertical_two_port_box_ports(
        block, source_id=source_id
    )
    vertical_box_applied = bool(
        vertical_box_ports
        and _has_vertical_two_port_box_topology(
            shape_features, port_count=len(vertical_box_ports)
        )
    )
    if vertical_box_applied:
        ports = list(vertical_box_ports)
        notes = (
            *notes,
            "Replaced outer-box corners with two independent numbered midpoint contacts.",
        )
        geometry_summary["selected_port_count"] = len(ports)
        geometry_summary["vertical_two_port_box_port_count"] = len(ports)
    two_row_box_ports = _propose_named_two_row_box_ports(
        block, source_id=source_id
    )
    two_row_box_applied = bool(
        two_row_box_ports and _has_named_two_row_box_topology(
            shape_features, port_count=len(two_row_box_ports)
        )
    )
    if two_row_box_applied:
        ports = list(two_row_box_ports)
        notes = (
            *notes,
            "Replaced outer-box extremes with two independent row attachment ports.",
        )
        geometry_summary["selected_port_count"] = len(ports)
        geometry_summary["named_two_row_box_port_count"] = len(ports)
    numbered_contact_ports = _propose_numbered_contact_grid_ports(
        block, source_id=source_id
    )
    numbered_contact_applied = bool(
        numbered_contact_ports
        and (
            len(numbered_contact_ports) <= 8
            or _is_numbered_round_contact_array_geometry(
                shape_features, port_count=len(numbered_contact_ports)
            )
            or _is_functional_round_contact_array_geometry(
                shape_features, port_count=len(numbered_contact_ports)
            )
        )
    )
    if numbered_contact_applied:
        ports = list(numbered_contact_ports)
        notes = (
            *notes,
            "Replaced free-end extremes with numbered closed-contact grid ports.",
        )
        geometry_summary["selected_port_count"] = len(ports)
        geometry_summary["numbered_contact_grid_port_count"] = len(ports)
    geometry_summary = {
        **geometry_summary,
        "entity_counts": entity_counts,
        "shape_features": shape_features,
    }
    status = "PROPOSED" if ports else "EMPTY"
    return SymbolPortProposal(
        definition_name=definition_name,
        definition_fingerprint=definition_fingerprint,
        source_dxf=str(source_dxf) if source_dxf is not None else None,
        ports=tuple(ports),
        method=(
            "numbered_contact_grid_v1"
            if numbered_contact_applied
            else "horizontal_numbered_two_circle_box_ports_v1"
            if horizontal_circle_box_applied
            else "vertical_two_port_box_ports_v1"
            if vertical_box_applied
            else "named_two_row_box_ports_v1"
            if two_row_box_applied
            else "free_endpoint_extremes_v1"
        ),
        status=status,
        notes=notes,
        geometry_summary=geometry_summary,
    )


def _propose_single_row_contact_mechanism_port(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Select the outer edge of the one line-bound contact in a row mechanism."""

    circles: list[tuple[tuple[float, float], float]] = []
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    contacts: list[tuple[tuple[float, float], tuple[tuple[float, float], ...], str]] = []
    for entity in block:
        entity_type = str(entity.dxftype()).upper()
        try:
            if entity_type == "CIRCLE":
                center = entity.dxf.center
                circles.append(
                    ((float(center.x), float(center.y)), float(entity.dxf.radius))
                )
            elif entity_type == "LINE":
                start, end = entity.dxf.start, entity.dxf.end
                lines.append(
                    (
                        (float(start.x), float(start.y)),
                        (float(end.x), float(end.y)),
                    )
                )
            elif entity_type == "LWPOLYLINE" and bool(
                getattr(entity, "closed", False)
            ):
                points = list(entity.get_points("xyb"))
                if len(points) != 2 or not any(
                    abs(float(point[2])) > 1e-9 for point in points
                ):
                    continue
                vertices = tuple(
                    (float(point[0]), float(point[1])) for point in points
                )
                contacts.append(
                    (
                        (
                            (vertices[0][0] + vertices[1][0]) / 2.0,
                            (vertices[0][1] + vertices[1][1]) / 2.0,
                        ),
                        vertices,
                        str(getattr(entity.dxf, "handle", "") or ""),
                    )
                )
        except (AttributeError, IndexError, TypeError, ValueError):
            return ()
    if len(circles) != 1 or len(lines) != 2 or len(contacts) != 2:
        return ()
    circle_center, circle_radius = circles[0]
    if circle_radius <= 1e-9:
        return ()
    endpoint_tolerance = circle_radius * 0.04
    line_endpoints = [point for line in lines for point in line]
    bound_contacts = [
        contact
        for contact in contacts
        if min(
            math.hypot(contact[0][0] - point[0], contact[0][1] - point[1])
            for point in line_endpoints
        )
        <= endpoint_tolerance
    ]
    if len(bound_contacts) != 1:
        return ()
    center, _vertices, handle = bound_contacts[0]
    outward_x = center[0] - circle_center[0]
    outward_y = center[1] - circle_center[1]
    outward_length = math.hypot(outward_x, outward_y)
    if outward_length <= 1e-9:
        return ()
    outward = (outward_x / outward_length, outward_y / outward_length)
    return (
        ProposedPort(
            port_id="RP1",
            local_position=(center[0], center[1], 0.0),
            outward_direction=(outward[0], outward[1], 0.0),
            port_type="ELECTRICAL",
            confidence=0.98,
            evidence_codes=(
                "SINGLE_ROW_CONTACT_MECHANISM",
                "LINE_BOUND_OUTER_CONTACT",
            ),
            source_ids=tuple(value for value in (source_id, handle) if value),
            notes="One named row port maps only to its same-side external line.",
            attachment_side="row_external",
        ),
    )


def _propose_horizontal_numbered_two_circle_box_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Select the two outward contacts paired with numbered circle cells."""

    circles: list[tuple[tuple[float, float], str]] = []
    contacts: list[tuple[tuple[float, float], str]] = []
    labels: list[tuple[str, tuple[float, float], str]] = []
    for entity in block:
        entity_type = str(entity.dxftype()).upper()
        handle = str(getattr(entity.dxf, "handle", "") or "")
        try:
            if entity_type == "CIRCLE":
                center = entity.dxf.center
                circles.append(((float(center.x), float(center.y)), handle))
            elif entity_type == "LWPOLYLINE" and bool(
                getattr(entity, "closed", False)
            ):
                points = list(entity.get_points("xyb"))
                if len(points) != 2 or not any(
                    abs(float(point[2])) > 1e-9 for point in points
                ):
                    continue
                contacts.append(
                    (
                        (
                            (float(points[0][0]) + float(points[1][0])) / 2.0,
                            (float(points[0][1]) + float(points[1][1])) / 2.0,
                        ),
                        handle,
                    )
                )
            elif entity_type in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                value = (
                    str(entity.plain_text())
                    if hasattr(entity, "plain_text")
                    else str(getattr(entity.dxf, "text", ""))
                ).strip()
                if value not in {"1", "2"}:
                    continue
                insert = entity.dxf.insert
                labels.append((value, (float(insert.x), float(insert.y)), handle))
        except (AttributeError, IndexError, TypeError, ValueError):
            return ()
    if (
        len(circles) != 2
        or len(contacts) != 2
        or {value for value, _, _ in labels} != {"1", "2"}
    ):
        return ()
    used_circles: set[int] = set()
    used_contacts: set[int] = set()
    ports: list[ProposedPort] = []
    for value, label_position, text_handle in sorted(labels):
        _, circle_index = min(
            (
                (math.hypot(center[0] - label_position[0], center[1] - label_position[1]), index)
                for index, (center, _) in enumerate(circles)
                if index not in used_circles
            ),
            key=lambda item: item[0],
        )
        circle_center, circle_handle = circles[circle_index]
        _, contact_index = min(
            (
                (math.hypot(center[0] - circle_center[0], center[1] - circle_center[1]), index)
                for index, (center, _) in enumerate(contacts)
                if index not in used_contacts
            ),
            key=lambda item: item[0],
        )
        contact_center, contact_handle = contacts[contact_index]
        dx = contact_center[0] - circle_center[0]
        dy = contact_center[1] - circle_center[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return ()
        used_circles.add(circle_index)
        used_contacts.add(contact_index)
        ports.append(
            ProposedPort(
                port_id=f"JR{value}",
                local_position=(contact_center[0], contact_center[1], 0.0),
                outward_direction=(dx / length, dy / length, 0.0),
                port_type="ELECTRICAL",
                confidence=0.99,
                evidence_codes=(
                    "HORIZONTAL_NUMBERED_TWO_CIRCLE_BOX",
                    "CIRCLE_BOUND_OUTER_CONTACT",
                    f"PORT_SLOT_{value}",
                    "NO_INTERNAL_CONNECTIVITY",
                ),
                source_ids=tuple(
                    value
                    for value in (
                        source_id,
                        circle_handle,
                        contact_handle,
                        text_handle,
                    )
                    if value
                ),
                notes="Independent numbered circle-box port; map outward only.",
                component_pin=value,
                attachment_side="circle_outward",
            )
        )
    return tuple(ports) if len(ports) == 2 else ()


def _propose_vertical_two_port_box_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Select the two midpoint contacts of a numbered vertical box."""

    contacts: list[tuple[tuple[float, float], str]] = []
    labels: list[tuple[str, tuple[float, float], str]] = []
    for entity in block:
        entity_type = str(entity.dxftype()).upper()
        handle = str(getattr(entity.dxf, "handle", "") or "")
        try:
            if entity_type == "LWPOLYLINE" and bool(
                getattr(entity, "closed", False)
            ):
                points = list(entity.get_points("xyb"))
                if len(points) != 2 or not any(
                    abs(float(point[2])) > 1e-9 for point in points
                ):
                    continue
                contacts.append(
                    (
                        (
                            (float(points[0][0]) + float(points[1][0])) / 2.0,
                            (float(points[0][1]) + float(points[1][1])) / 2.0,
                        ),
                        handle,
                    )
                )
            elif entity_type in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                value = (
                    str(entity.plain_text())
                    if hasattr(entity, "plain_text")
                    else str(getattr(entity.dxf, "text", ""))
                ).strip()
                if value not in {"1", "2"}:
                    continue
                insert = entity.dxf.insert
                labels.append(
                    (value, (float(insert.x), float(insert.y)), handle)
                )
        except (AttributeError, IndexError, TypeError, ValueError):
            continue
    if len(contacts) != 2 or {value for value, _, _ in labels} != {"1", "2"}:
        return ()
    center = (
        sum(point[0] for point, _ in contacts) / 2.0,
        sum(point[1] for point, _ in contacts) / 2.0,
    )
    assigned: dict[str, tuple[tuple[float, float], str, str]] = {}
    used_contacts: set[int] = set()
    for value, label_point, text_handle in sorted(labels):
        distance, index = min(
            (
                math.hypot(
                    contact[0][0] - label_point[0],
                    contact[0][1] - label_point[1],
                ),
                contact_index,
            )
            for contact_index, contact in enumerate(contacts)
            if contact_index not in used_contacts
        )
        del distance
        used_contacts.add(index)
        assigned[value] = (contacts[index][0], contacts[index][1], text_handle)
    if set(assigned) != {"1", "2"}:
        return ()
    ports: list[ProposedPort] = []
    for value in ("1", "2"):
        point, contact_handle, text_handle = assigned[value]
        dx, dy = point[0] - center[0], point[1] - center[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return ()
        ports.append(
            ProposedPort(
                port_id=f"VP{value}",
                local_position=(point[0], point[1], 0.0),
                outward_direction=(dx / length, dy / length, 0.0),
                port_type="ELECTRICAL",
                confidence=0.98,
                evidence_codes=(
                    "NUMBERED_VERTICAL_BOX_CONTACT",
                    "OUTWARD_FROM_BOX_CENTER",
                ),
                source_ids=(source_id, contact_handle, text_handle),
                notes="Independent numbered box port; map outward only and never union through the body.",
                component_pin=value,
                attachment_side="upper" if value == "1" else "lower",
            )
        )
    return tuple(ports)


def _propose_named_two_row_box_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Select the two repeated row contacts, excluding the outer box corners."""

    bodies: list[list[tuple[float, float]]] = []
    contacts: list[tuple[tuple[float, float], str]] = []
    for entity in block:
        if str(entity.dxftype()).upper() != "LWPOLYLINE" or not bool(
            getattr(entity, "closed", False)
        ):
            continue
        try:
            points = list(entity.get_points("xyb"))
            bulged = any(abs(float(point[2])) > 1e-9 for point in points)
        except Exception:
            continue
        if bulged and len(points) == 2:
            contacts.append(
                (
                    (
                        (float(points[0][0]) + float(points[1][0])) / 2.0,
                        (float(points[0][1]) + float(points[1][1])) / 2.0,
                    ),
                    str(getattr(entity.dxf, "handle", "") or ""),
                )
            )
        elif not bulged and len(points) == 4:
            bodies.append([(float(point[0]), float(point[1])) for point in points])
    if len(bodies) != 1 or len(contacts) != 4:
        return ()
    body = bodies[0]
    center = (
        (min(point[0] for point in body) + max(point[0] for point in body)) / 2.0,
        (min(point[1] for point in body) + max(point[1] for point in body)) / 2.0,
    )
    edges = []
    for start, end in zip(body, body[1:] + body[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return ()
        edges.append((dx / length, dy / length, length))
    short = min(edges, key=lambda item: item[2])
    axis_x, axis_y = short[0], short[1]
    normal_x, normal_y = -axis_y, axis_x
    projected = []
    for point, handle in contacts:
        dx, dy = point[0] - center[0], point[1] - center[1]
        projected.append(
            (
                dx * axis_x + dy * axis_y,
                dx * normal_x + dy * normal_y,
                point,
                handle,
            )
        )
    groups: list[list[tuple[float, float, tuple[float, float], str]]] = []
    tolerance = min(item[2] for item in edges) * 0.03
    for item in sorted(projected, key=lambda value: value[0]):
        if groups and abs(
            item[0] - sum(value[0] for value in groups[-1]) / len(groups[-1])
        ) <= tolerance:
            groups[-1].append(item)
        else:
            groups.append([item])
    if len(groups) != 2 or any(len(group) != 2 for group in groups):
        return ()
    port_group = min(
        groups, key=lambda group: abs(sum(item[1] for item in group) / len(group))
    )
    group_midpoint = (
        sum(item[2][0] for item in port_group) / 2.0,
        sum(item[2][1] for item in port_group) / 2.0,
    )
    outward_x = group_midpoint[0] - center[0]
    outward_y = group_midpoint[1] - center[1]
    outward_length = math.hypot(outward_x, outward_y)
    if outward_length <= 1e-9:
        return ()
    ports = []
    for slot, item in enumerate(
        sorted(port_group, key=lambda value: value[1], reverse=True), start=1
    ):
        ports.append(
            ProposedPort(
                port_id=f"BP{slot}",
                local_position=(item[2][0], item[2][1], 0.0),
                outward_direction=(
                    outward_x / outward_length,
                    outward_y / outward_length,
                    0.0,
                ),
                port_type="ELECTRICAL",
                confidence=0.98,
                evidence_codes=(
                    "NAMED_TWO_ROW_BOX",
                    "REPEATED_ROW_CONTACT",
                    f"PORT_SLOT_{slot}",
                ),
                source_ids=tuple(value for value in (source_id, item[3]) if value),
                notes="Independent row attachment; no row-to-row connectivity inferred.",
                component_pin=str(slot),
                attachment_side="upper" if slot == 1 else "lower",
            )
        )
    return tuple(ports)


def _propose_numbered_contact_grid_ports(
    block: Any, *, source_id: str
) -> tuple[ProposedPort, ...]:
    """Bind block-local numeric slots to closed round contacts.

    This is definition geometry only. Instance labels and external endpoints are
    still supplied by component_mapping; the helper never infers body-internal
    connectivity.
    """

    labels: list[tuple[str, tuple[float, float]]] = []
    contact_candidates: list[tuple[tuple[float, float], float]] = []
    for entity in block:
        entity_type = str(entity.dxftype()).upper()
        if entity_type in {"TEXT", "ATTRIB", "ATTDEF"}:
            try:
                value = str(entity.dxf.text).strip()
                insert = entity.dxf.insert
            except Exception:
                continue
            normalized_value = value.upper()
            if re.fullmatch(r"[1-9][0-9]?", normalized_value) or normalized_value in {
                "C+", "G-", "R-"
            }:
                labels.append((normalized_value, (float(insert.x), float(insert.y))))
        elif entity_type == "LWPOLYLINE" and bool(
            getattr(entity, "closed", False)
        ):
            try:
                points = list(entity.get_points("xyb"))
                if not points or not any(abs(float(point[2])) > 1e-9 for point in points):
                    continue
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
            except Exception:
                continue
            chord_diameter = max(
                (
                    math.hypot(
                        float(right[0]) - float(left[0]),
                        float(right[1]) - float(left[1]),
                    )
                    for left_index, left in enumerate(points)
                    for right in points[left_index + 1 :]
                ),
                default=0.0,
            )
            contact_candidates.append(
                (
                    ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0),
                    chord_diameter / 2.0,
                )
            )
    label_count = len(labels)
    functional_order = ("1", "2", "3", "4", "5", "6", "7", "8", "C+", "G-", "R-")
    functional_labels = {value for value, _ in labels} == set(functional_order)
    if not functional_labels and not (
        label_count in {4, 6, 8}
        or 8 <= label_count <= 32 and label_count % 2 == 0
    ):
        return ()
    labels.sort(
        key=lambda item: (
            functional_order.index(item[0])
            if functional_labels
            else int(item[0])
        )
    )
    label_values = [value for value, _ in labels]
    if functional_labels:
        if tuple(label_values) != functional_order:
            return ()
    elif [int(value) for value in label_values] != list(
        range(int(label_values[0]), int(label_values[0]) + len(labels))
    ):
        return ()
    has_body = len(contact_candidates) == label_count + 1
    if len(contact_candidates) == label_count:
        contacts = [center for center, _ in contact_candidates]
    elif has_body:
        ordered_candidates = sorted(contact_candidates, key=lambda item: item[1])
        small = ordered_candidates[:label_count]
        radii = [radius for _, radius in small]
        if (
            min(radii) <= 1e-9
            or max(radii) / min(radii) > 1.05
            or ordered_candidates[-1][1] / max(radii) < 20.0
        ):
            return ()
        contacts = [center for center, _ in small]
    else:
        return ()
    if has_body and not functional_labels and [int(value) for value in label_values] != list(
        range(1, label_count + 1)
    ):
        return ()

    remaining = set(range(len(contacts)))
    assigned_contacts: list[tuple[float, float]] = []
    best_score = 0.0
    for _, label_position in labels:
        contact_index = min(
            remaining,
            key=lambda index: _distance(label_position, contacts[index]),
        )
        remaining.remove(contact_index)
        assigned_contacts.append(contacts[contact_index])
        best_score += _distance(label_position, contacts[contact_index])
    all_x = [point[0] for point in contacts]
    all_y = [point[1] for point in contacts]
    extent = max(max(all_x) - min(all_x), max(all_y) - min(all_y))
    if extent <= 1e-9 or best_score / len(labels) > extent * 0.5:
        return ()

    ports = []
    side_axis: tuple[float, float] | None = None
    grid_center = (
        sum(point[0] for point in contacts) / len(contacts),
        sum(point[1] for point in contacts) / len(contacts),
    )
    if len(contacts) == 8 and not has_body:
        covariance_xx = sum(
            (point[0] - grid_center[0]) ** 2 for point in contacts
        ) / len(contacts)
        covariance_yy = sum(
            (point[1] - grid_center[1]) ** 2 for point in contacts
        ) / len(contacts)
        covariance_xy = sum(
            (point[0] - grid_center[0]) * (point[1] - grid_center[1])
            for point in contacts
        ) / len(contacts)
        angle = 0.5 * math.atan2(
            2.0 * covariance_xy, covariance_xx - covariance_yy
        )
        side_axis = (math.cos(angle), math.sin(angle))
    for (slot, label_position), contact in zip(labels, assigned_contacts):
        outward_direction = _normalize(
            (
                contact[0] - label_position[0],
                contact[1] - label_position[1],
            )
        )
        if side_axis is not None:
            projection = (
                (contact[0] - grid_center[0]) * side_axis[0]
                + (contact[1] - grid_center[1]) * side_axis[1]
            )
            if abs(projection) <= 1e-9:
                return ()
            sign = 1.0 if projection > 0.0 else -1.0
            outward_direction = (side_axis[0] * sign, side_axis[1] * sign, 0.0)
        ports.append(
            ProposedPort(
                port_id=f"MP{slot}",
                local_position=(contact[0], contact[1], 0.0),
                outward_direction=outward_direction,
                port_type="ELECTRICAL",
                confidence=0.99 if has_body else 0.9,
                evidence_codes=(
                    "NUMBERED_CONTACT_GRID",
                    "CLOSED_BULGED_CONTACT",
                    f"PORT_SLOT_{slot}",
                ),
                source_ids=(source_id,),
                notes="Numbered external contact; no internal connectivity inferred.",
                component_pin=str(slot),
            )
        )
    return tuple(ports)


def _unique_proposal_for_instance(
    instance: Mapping[str, Any],
    *,
    proposals_by_key: Mapping[tuple[str, str], list[dict[str, Any]]],
    proposals_by_fingerprint: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    """Resolve one proposal using the same identity safeguards as port binding."""

    file_id = str(instance.get("file_id") or "").strip()
    name = str(instance.get("definition_name") or "").strip()
    fingerprint = str(instance.get("definition_fingerprint") or "").strip().casefold()
    if not file_id or not name:
        return None

    name_matches = list(proposals_by_key.get((file_id, name.casefold()), ()))
    if fingerprint:
        exact_matches = list(
            proposals_by_fingerprint.get((file_id, fingerprint), ())
        )
        named_exact_matches = [
            row
            for row in exact_matches
            if str(row.get("definition_name") or "").strip().casefold()
            == name.casefold()
        ]
        if len(named_exact_matches) == 1:
            return named_exact_matches[0]
        if len(exact_matches) == 1:
            return exact_matches[0]
        unversioned = [
            row
            for row in name_matches
            if not str(row.get("definition_fingerprint") or "").strip()
        ]
        return unversioned[0] if len(unversioned) == 1 else None
    return name_matches[0] if len(name_matches) == 1 else None


def _instance_has_whole_symbol_ignored_ancestor(
    instance: Mapping[str, Any],
    *,
    instances_by_nested_path: Mapping[
        tuple[str, str, str], Mapping[str, Any]
    ],
    proposals_by_key: Mapping[tuple[str, str], list[dict[str, Any]]],
    proposals_by_fingerprint: Mapping[tuple[str, str], list[dict[str, Any]]],
    behavior_cache: dict[tuple[str, str, str], dict[str, Any] | None],
) -> bool:
    """Inherit authoritative whole-symbol IGNORE through every ancestor level."""

    file_id = str(instance.get("file_id") or "").strip()
    sheet_id = str(instance.get("sheet_id") or "").strip()
    nested_path = str(instance.get("nested_path") or "").strip()
    while "/" in nested_path:
        nested_path = nested_path.rsplit("/", 1)[0]
        ancestor = instances_by_nested_path.get((file_id, sheet_id, nested_path))
        if ancestor is None:
            continue
        fingerprint = str(
            ancestor.get("definition_fingerprint") or ""
        ).strip().casefold()
        cache_key = (
            file_id,
            str(ancestor.get("definition_name") or "").strip().casefold(),
            fingerprint,
        )
        if cache_key not in behavior_cache:
            proposal = _unique_proposal_for_instance(
                ancestor,
                proposals_by_key=proposals_by_key,
                proposals_by_fingerprint=proposals_by_fingerprint,
            )
            if proposal is None:
                behavior_cache[cache_key] = None
            else:
                family = classify_definition_family(
                    proposal, fingerprint=fingerprint or None
                )
                behavior_cache[cache_key] = evaluate_symbol_behavior(
                    family,
                    reviewed_policy=human_symbol_port_policy(fingerprint),
                )
        behavior = behavior_cache[cache_key]
        if (
            behavior is not None
            and behavior.get("behavior_mode") == "IGNORE"
            and behavior.get("suppressed_by_policy") is True
        ):
            return True
    return False


def build_instance_port_network_candidates(
    definition_proposals: Any,
    instances: Any,
    texts: Any,
    lines: Any,
    network_members: Any,
    *,
    component_pairs: Any = None,
    label_radius: float = 3.5,
    component_label_radius: float = 25.0,
    terminal_label_ambiguity_tolerance: float = 0.5,
    endpoint_tolerance: float = 0.05,
) -> list[dict[str, Any]]:
    """Bind definition ports to instance labels and external networks.

    The result is shadow-only and never infers conductivity through a symbol.
    """

    proposal_rows = _mapping_rows(definition_proposals)
    instance_rows = _mapping_rows(instances)
    text_rows = _mapping_rows(texts)
    line_rows = _mapping_rows(lines)
    member_rows = _mapping_rows(network_members)
    component_pair_rows = _mapping_rows(component_pairs)

    networks_by_handle: dict[str, set[str]] = defaultdict(set)
    for row in member_rows:
        if str(row.get("member_type") or "") != "SOURCE_LINE":
            continue
        handle = str(row.get("source_handle") or "").strip()
        network_id = str(row.get("electrical_network_id") or "").strip()
        if handle and network_id:
            networks_by_handle[handle].add(network_id)

    component_mapping_by_port: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in component_pair_rows:
        if str(row.get("pair_kind") or "") != "component_mapping":
            continue
        sheet_key = str(row.get("sheet_id") or "").strip()
        port_key = str(row.get("left_value") or "").strip()
        endpoint = str(row.get("right_value") or "").strip()
        if sheet_key and port_key and endpoint:
            component_mapping_by_port[(sheet_key, port_key)].append(row)

    all_proposals_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    all_proposals_by_fingerprint: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    proposals_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    proposals_by_fingerprint: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        file_id = str(row.get("file_id") or "").strip()
        name = str(row.get("definition_name") or "").strip()
        if not file_id or not name:
            continue
        fingerprint = str(row.get("definition_fingerprint") or "").strip().casefold()
        all_proposals_by_key[(file_id, name.casefold())].append(row)
        if fingerprint:
            all_proposals_by_fingerprint[(file_id, fingerprint)].append(row)
        if row.get("ports"):
            proposals_by_key[(file_id, name.casefold())].append(row)
            if fingerprint:
                proposals_by_fingerprint[(file_id, fingerprint)].append(row)

    instances_by_nested_path: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in instance_rows:
        nested_path = str(row.get("nested_path") or "").strip()
        if not nested_path:
            continue
        key = (
            str(row.get("file_id") or "").strip(),
            str(row.get("sheet_id") or "").strip(),
            nested_path,
        )
        instances_by_nested_path[key] = row

    numeric_label = re.compile(r"^[0-9]{1,3}$")
    terminal_designator = re.compile(
        r"^(?:[0-9]+[A-Za-z][A-Za-z0-9-]*|[A-Za-z]+[0-9][A-Za-z0-9-]*)$"
    )
    component_designator = re.compile(r"^\d+(?:-\d+)?[A-Za-z]{1,5}\d*$")
    short_alpha_component_designator = re.compile(r"^[A-Za-z]{2,5}$")
    single_alpha_component_designator = re.compile(r"^[A-Za-z]$")
    compound_endpoint_designator = re.compile(
        r"^[A-Za-z][A-Za-z0-9']*(?:-[A-Za-z0-9']+)+$"
    )
    hierarchical_endpoint_designator = re.compile(
        r"^\d+(?:-\d+)+[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*$"
    )
    hyphen_component_designator = re.compile(
        r"^[A-Za-z]{1,6}(?:-[A-Za-z]{1,6}){1,6}$"
    )
    apostrophe_component_designator = re.compile(r"^[A-Za-z]{1,4}'$")
    row_component_designator = re.compile(r"^(?:[A-Za-z]{1,5}|[A-Za-z]{1,4}')$")
    ancestor_behavior_cache: dict[tuple[str, str, str], dict[str, Any] | None] = {}
    candidates: list[dict[str, Any]] = []
    for instance in instance_rows:
        file_id = str(instance.get("file_id") or "").strip()
        sheet_id = str(instance.get("sheet_id") or "").strip()
        if _instance_has_whole_symbol_ignored_ancestor(
            instance,
            instances_by_nested_path=instances_by_nested_path,
            proposals_by_key=all_proposals_by_key,
            proposals_by_fingerprint=all_proposals_by_fingerprint,
            behavior_cache=ancestor_behavior_cache,
        ):
            continue
        name = str(instance.get("definition_name") or "").strip()
        instance_id = str(instance.get("symbol_instance_id") or "").strip()
        instance_handle = str(instance.get("entity_handle") or "").strip()
        instance_fingerprint = str(
            instance.get("definition_fingerprint") or ""
        ).strip().casefold()
        policy = human_symbol_port_policy(instance_fingerprint)
        name_matching = proposals_by_key.get((file_id, name.casefold()), [])
        matching = (
            proposals_by_fingerprint.get((file_id, instance_fingerprint), [])
            if instance_fingerprint
            else []
        )
        if matching and name_matching:
            named_exact_matches = [
                row
                for row in matching
                if str(row.get("definition_name") or "").strip().casefold()
                == name.casefold()
            ]
            if named_exact_matches:
                matching = named_exact_matches
        binding_status = "FINGERPRINT_EXACT"
        if not matching:
            unversioned = [
                row
                for row in name_matching
                if not str(row.get("definition_fingerprint") or "").strip()
            ]
            conflicting = [
                row
                for row in name_matching
                if str(row.get("definition_fingerprint") or "").strip()
                and str(row.get("definition_fingerprint") or "").strip().casefold()
                != instance_fingerprint
            ]
            if instance_fingerprint and conflicting and not unversioned:
                candidates.append(
                    {
                        "schema_version": "symbol-port-network-candidate-v1",
                        "candidate_id": f"SPNC:{instance_id or instance_handle}:BINDING",
                        "project_id": instance.get("project_id"),
                        "sheet_id": sheet_id,
                        "file_id": file_id,
                        "symbol_instance_id": instance_id or None,
                        "symbol_instance_handle": instance_handle or None,
                        "definition_name": name,
                        "definition_fingerprint": instance.get("definition_fingerprint"),
                        "proposal_fingerprints": sorted(
                            {
                                str(row.get("definition_fingerprint") or "")
                                for row in conflicting
                            }
                        ),
                        "binding_status": "REJECTED_FINGERPRINT_MISMATCH",
                        "relation_kind": "PROPOSAL_TO_INSTANCE_BINDING",
                        "status": "REJECTED_FINGERPRINT_MISMATCH",
                        "confidence": 0.0,
                        "evidence_codes": ["DEFINITION_FINGERPRINT_MISMATCH"],
                        "annotation_status": "MACHINE_PROPOSED",
                        "authority": "SHADOW_ONLY",
                        "shadow_only": True,
                        "internal_connectivity_inferred": False,
                        "electrical_union_eligible": False,
                        "critical_issue_eligible": False,
                    }
                )
                continue
            matching = unversioned if unversioned else name_matching
            binding_status = (
                "LEGACY_NAME_FALLBACK_UNVERIFIED"
                if matching
                else "UNRESOLVED"
            )
        if len(matching) != 1:
            continue
        family = classify_definition_family(
            matching[0], fingerprint=instance_fingerprint or None
        )
        behavior = evaluate_symbol_behavior(family, reviewed_policy=policy)
        family_id = str(family.get("family_id") or "")
        if behavior.get("suppressed_by_policy"):
            continue
        four_contact_terminal_geometry = _is_four_contact_terminal_geometry(
            matching[0].get("geometry_summary", {}).get("shape_features", {}),
            port_count=len(matching[0].get("ports") or []),
        )
        terminal_geometry = (
            is_high_confidence_terminal_geometry(matching[0])
            or four_contact_terminal_geometry
        )
        labelled_terminal = family_id.startswith("labelled_terminal.")
        component_port_model = family_id.startswith("component.external_")
        communication_panel_model = (
            family_id == "component.external_communication_panel.v1"
        )
        named_two_port_strip_model = (
            family_id in {"component.external_strip_two_port.v1", "component.external_wfs_polarity_two_port.v1"}
            and family.get("matched_family_rule_id")
            in {
                "four-contact-two-circle-named-strip-v1",
                "two-contact-mechanical-actuator-v1",
                "vertical-numbered-two-port-box-v1",
                "horizontal-numbered-two-circle-box-v1",
                "named-isolated-two-circle-two-port-v1",
                "fjl-two-circle-four-contact-line-bound-ports-v1",
                "wfs-rounded-polarity-axial-two-port-v1",
            }
        )
        wfs_polarity_model = (
            family_id == "component.external_wfs_polarity_two_port.v1"
            and family.get("matched_family_rule_id")
            == "wfs-rounded-polarity-axial-two-port-v1"
        )
        fjl_line_bound_model = (
            family_id == "component.external_strip_two_port.v1"
            and family.get("matched_family_rule_id")
            == "fjl-two-circle-four-contact-line-bound-ports-v1"
        )
        kk_of_selective_model = (
            family_id == "component.external_multi_port.v1"
            and str(family.get("matched_family_rule_id") or "").startswith(
                "kk-of-selective-"
            )
        )
        selective_component_model = fjl_line_bound_model or kk_of_selective_model
        two_contact_actuator_model = (
            family_id == "component.external_strip_two_port.v1"
            and family.get("matched_family_rule_id")
            == "two-contact-mechanical-actuator-v1"
        )
        named_two_row_box_model = (
            family_id == "component.external_strip_two_port.v1"
            and family.get("matched_family_rule_id")
            == "named-two-row-box-four-contact-v1"
        )
        vertical_two_port_box_model = (
            family_id == "component.external_strip_two_port.v1"
            and family.get("matched_family_rule_id")
            == "vertical-numbered-two-port-box-v1"
        )
        horizontal_numbered_two_circle_box_model = (
            family_id == "component.external_strip_two_port.v1"
            and family.get("matched_family_rule_id")
            == "horizontal-numbered-two-circle-box-v1"
        )
        single_row_contact_model = (
            family_id == "component.external_row_contact.v1"
            and family.get("matched_family_rule_id")
            == "single-row-circle-contact-mechanism-v1"
        )
        three_contact_socket_model = (
            family_id == "component.external_multi_port.v1"
            and family.get("matched_family_rule_id")
            == "three-contact-labelled-socket-v1"
        )
        four_contact_isolated_frame_model = (
            family_id == "component.external_multi_port.v1"
            and family.get("matched_family_rule_id")
            in {
                "four-contact-isolated-switch-frame-v1",
                "four-numbered-independent-contact-panel-v1",
                "eight-numbered-side-contact-panel-v1",
            }
        )
        eight_numbered_side_contact_panel_model = (
            family_id == "component.external_multi_port.v1"
            and family.get("matched_family_rule_id")
            == "eight-numbered-side-contact-panel-v1"
        )
        four_numbered_contact_panel_model = (
            family_id in {
                "component.external_multi_port.v1",
                "component.external_elxal5_b11_209b_circle_grid.v1",
                "component.external_elxal5_b11_209b_ellipse_grid.v1",
            }
            and family.get("matched_family_rule_id")
            == "four-numbered-independent-contact-panel-v1"
        )
        numbered_round_contact_array_model = (
            family_id == "component.external_multi_port.v1"
            and family.get("matched_family_rule_id")
            in {
                "numbered-round-contact-array-v1",
                "numbered-functional-contact-array-v1",
            }
        )
        functional_round_contact_array_model = (
            family_id == "component.external_multi_port.v1"
            and family.get("matched_family_rule_id")
            == "numbered-functional-contact-array-v1"
        )
        if single_row_contact_model:
            nested_path = str(instance.get("nested_path") or "").strip()
            if "/" in nested_path:
                parent_path = nested_path.rsplit("/", 1)[0]
                parent_instance = instances_by_nested_path.get(
                    (file_id, sheet_id, parent_path)
                )
                parent_fingerprint = str(
                    (parent_instance or {}).get("definition_fingerprint") or ""
                ).strip().casefold()
                parent_matching = proposals_by_fingerprint.get(
                    (file_id, parent_fingerprint), []
                )
                if len(parent_matching) == 1:
                    parent_family = classify_definition_family(
                        parent_matching[0], fingerprint=parent_fingerprint or None
                    )
                    if (
                        parent_family.get("matched_family_rule_id")
                        == "named-two-row-box-four-contact-v1"
                    ):
                        continue
        matrix = _instance_matrix(instance.get("transform_json"))
        if matrix is None:
            continue
        ports = [
            dict(row)
            for row in matching[0].get("ports") or []
            if isinstance(row, Mapping)
        ]
        world_ports: list[tuple[float, float, float]] = []
        world_outward_directions: list[tuple[float, float] | None] = []
        for port in ports:
            local = port.get("local_position") or []
            if not isinstance(local, Sequence) or len(local) < 2:
                world_ports.append((math.nan, math.nan, math.nan))
                world_outward_directions.append(None)
                continue
            local_point = (
                float(local[0]),
                float(local[1]),
                float(local[2]) if len(local) > 2 else 0.0,
            )
            world = _transform_point(matrix, local_point)
            world_ports.append(world)
            outward = port.get("outward_direction") or []
            if isinstance(outward, Sequence) and len(outward) >= 2:
                local_tip = (
                    local_point[0] + float(outward[0]),
                    local_point[1] + float(outward[1]),
                    local_point[2] + (float(outward[2]) if len(outward) > 2 else 0.0),
                )
                world_tip = _transform_point(matrix, local_tip)
                dx = world_tip[0] - world[0]
                dy = world_tip[1] - world[1]
                norm = math.hypot(dx, dy)
                world_outward_directions.append(
                    (dx / norm, dy / norm) if norm > 1e-12 else None
                )
            else:
                world_outward_directions.append(None)

        effective_endpoint_tolerance = endpoint_tolerance
        if terminal_geometry:
            shape = matching[0].get("geometry_summary", {}).get("shape_features", {})
            radii = [
                float(value)
                for value in shape.get("arc_radii", [])
                if isinstance(value, (int, float)) and float(value) > 0.0
            ]
            if radii:
                origin = _transform_point(matrix, (0.0, 0.0, 0.0))
                unit_x = _transform_point(matrix, (1.0, 0.0, 0.0))
                unit_y = _transform_point(matrix, (0.0, 1.0, 0.0))
                scale = max(
                    math.hypot(unit_x[0] - origin[0], unit_x[1] - origin[1]),
                    math.hypot(unit_y[0] - origin[0], unit_y[1] - origin[1]),
                )
                effective_endpoint_tolerance = max(
                    endpoint_tolerance,
                    (sum(radii) / len(radii)) * scale * 0.08,
                )

        eligible_texts: list[tuple[str, float, float, dict[str, Any]]] = []
        panel_endpoint_texts: list[
            tuple[str, float, float, dict[str, Any]]
        ] = []
        terminal_labels: list[tuple[float, str, dict[str, Any]]] = []
        component_labels: list[tuple[float, str, dict[str, Any]]] = []
        socket_pin_texts: list[tuple[str, float, float, dict[str, Any]]] = []
        socket_endpoint_texts: list[tuple[str, float, float, dict[str, Any]]] = []
        external_component_texts: list[
            tuple[str, float, float, dict[str, Any]]
        ] = []
        for text_row in text_rows:
            if str(text_row.get("sheet_id") or "") != sheet_id:
                continue
            if file_id and str(text_row.get("file_id") or "") != file_id:
                continue
            value = str(
                text_row.get("normalized_text") or text_row.get("text") or ""
            ).strip()
            component_value = value.strip(" @&").strip()
            try:
                x = float(text_row.get("insert_x"))
                y = float(text_row.get("insert_y"))
            except (TypeError, ValueError):
                continue
            if labelled_terminal and terminal_designator.fullmatch(value):
                terminal_labels.append((0.0, value, text_row))
            if component_port_model and (
                component_designator.fullmatch(component_value)
                or (
                    (
                        named_two_port_strip_model
                        or three_contact_socket_model
                        or four_contact_isolated_frame_model
                        or kk_of_selective_model
                        or numbered_round_contact_array_model
                    )
                    and (
                        short_alpha_component_designator.fullmatch(component_value)
                        or (
                            eight_numbered_side_contact_panel_model
                            and single_alpha_component_designator.fullmatch(component_value)
                        )
                    )
                )
                or (
                    (named_two_row_box_model or vertical_two_port_box_model)
                    and apostrophe_component_designator.fullmatch(component_value)
                )
                or (
                    single_row_contact_model
                    and row_component_designator.fullmatch(component_value)
                )
            ):
                component_labels.append((0.0, component_value, text_row))
            if three_contact_socket_model and value.upper() in {"E", "L", "N"}:
                socket_pin_texts.append((value.upper(), x, y, text_row))
            endpoint_value = value.rstrip().removesuffix("&").rstrip()
            if (
                three_contact_socket_model
                or four_contact_isolated_frame_model
                or two_contact_actuator_model
                or selective_component_model
                or numbered_round_contact_array_model
            ) and (
                terminal_designator.fullmatch(endpoint_value)
                or (
                    functional_round_contact_array_model
                    and hierarchical_endpoint_designator.fullmatch(endpoint_value)
                )
                or (
                    eight_numbered_side_contact_panel_model
                    and compound_endpoint_designator.fullmatch(endpoint_value)
                )
            ):
                socket_endpoint_texts.append((endpoint_value, x, y, text_row))
            if (
                four_contact_isolated_frame_model
                and hyphen_component_designator.fullmatch(value)
            ):
                external_component_texts.append((value, x, y, text_row))
            if numeric_label.fullmatch(value):
                eligible_texts.append((value, x, y, text_row))
            if communication_panel_model and _is_communication_panel_external_endpoint(
                value
            ):
                panel_endpoint_texts.append(
                    (
                        _clean_communication_panel_endpoint(value),
                        x,
                        y,
                        text_row,
                    )
                )

        if labelled_terminal:
            center = _transform_point(matrix, (0.0, 0.0, 0.0))
            terminal_labels = sorted(
                [
                    (
                        math.hypot(center[0] - float(row.get("insert_x")), center[1] - float(row.get("insert_y"))),
                        value,
                        row,
                    )
                    for _, value, row in terminal_labels
                ],
                key=lambda item: (item[0], item[1]),
            )
        terminal_labels_in_range = [
            item for item in terminal_labels if item[0] <= label_radius * 2.0
        ]
        nearest_terminal_by_value: dict[str, tuple[float, str, dict[str, Any]]] = {}
        for item in terminal_labels_in_range:
            nearest_terminal_by_value.setdefault(item[1], item)
        distinct_terminal_labels = sorted(
            nearest_terminal_by_value.values(), key=lambda item: (item[0], item[1])
        )
        terminal_label_ambiguous = bool(
            len(distinct_terminal_labels) > 1
            and distinct_terminal_labels[1][0] - distinct_terminal_labels[0][0]
            <= terminal_label_ambiguity_tolerance
        )
        bound_terminal = (
            distinct_terminal_labels[0]
            if distinct_terminal_labels and not terminal_label_ambiguous
            else None
        )
        if component_port_model:
            center = (
                (
                    sum(point[0] for point in world_ports) / len(world_ports),
                    sum(point[1] for point in world_ports) / len(world_ports),
                    0.0,
                )
                if (
                    named_two_port_strip_model
                    or named_two_row_box_model
                    or single_row_contact_model
                    or three_contact_socket_model
                    or four_contact_isolated_frame_model
                    or kk_of_selective_model
                    or numbered_round_contact_array_model
                )
                and world_ports
                else _transform_point(matrix, (0.0, 0.0, 0.0))
            )
            measured_component_labels = [
                (
                    math.hypot(
                        center[0] - float(row.get("insert_x")),
                        center[1] - float(row.get("insert_y")),
                    ),
                    value,
                    row,
                )
                for _, value, row in component_labels
            ]
            if four_numbered_contact_panel_model:
                pin_world = {
                    int(str(port.get("component_pin") or "")): world
                    for port, world in zip(ports, world_ports)
                    if str(port.get("component_pin") or "").isdigit()
                    and math.isfinite(world[0])
                    and math.isfinite(world[1])
                }
                ordered_pins = sorted(pin_world)
                if len(ordered_pins) == 4:
                    upper = (
                        sum(pin_world[pin][0] for pin in ordered_pins[:2]) / 2.0,
                        sum(pin_world[pin][1] for pin in ordered_pins[:2]) / 2.0,
                    )
                    lower = (
                        sum(pin_world[pin][0] for pin in ordered_pins[2:]) / 2.0,
                        sum(pin_world[pin][1] for pin in ordered_pins[2:]) / 2.0,
                    )
                    axis = (upper[0] - lower[0], upper[1] - lower[1])
                    axis_length = math.hypot(axis[0], axis[1])
                    if axis_length > 1e-9:
                        axis = (axis[0] / axis_length, axis[1] / axis_length)
                        filtered_labels = []
                        for distance_value, value, row in measured_component_labels:
                            dx = float(row.get("insert_x")) - center[0]
                            dy = float(row.get("insert_y")) - center[1]
                            forward = dx * axis[0] + dy * axis[1]
                            lateral = abs(dx * axis[1] - dy * axis[0])
                            if (
                                0.0 < forward <= component_label_radius
                                and lateral <= component_label_radius * 0.6
                            ):
                                filtered_labels.append(
                                    (distance_value, value, row)
                                )
                        measured_component_labels = filtered_labels
            elif eight_numbered_side_contact_panel_model:
                pin_world = {
                    int(str(port.get("component_pin") or "")): world
                    for port, world in zip(ports, world_ports)
                    if str(port.get("component_pin") or "").isdigit()
                    and math.isfinite(world[0])
                    and math.isfinite(world[1])
                }
                if {2, 3, 6, 7}.issubset(pin_world):
                    upper = (
                        (pin_world[6][0] + pin_world[7][0]) / 2.0,
                        (pin_world[6][1] + pin_world[7][1]) / 2.0,
                    )
                    lower = (
                        (pin_world[2][0] + pin_world[3][0]) / 2.0,
                        (pin_world[2][1] + pin_world[3][1]) / 2.0,
                    )
                    axis = (upper[0] - lower[0], upper[1] - lower[1])
                    axis_length = math.hypot(axis[0], axis[1])
                    if axis_length > 1e-9:
                        axis = (axis[0] / axis_length, axis[1] / axis_length)
                        body_half_height = axis_length / 2.0
                        filtered_labels = []
                        for distance_value, value, row in measured_component_labels:
                            dx = float(row.get("insert_x")) - center[0]
                            dy = float(row.get("insert_y")) - center[1]
                            forward = dx * axis[0] + dy * axis[1]
                            lateral = abs(dx * axis[1] - dy * axis[0])
                            if (
                                body_half_height * 1.05 < forward <= component_label_radius
                                and lateral <= max(body_half_height, 3.0)
                            ):
                                filtered_labels.append((distance_value, value, row))
                        measured_component_labels = filtered_labels
            elif functional_round_contact_array_model:
                pin_world = {
                    str(port.get("component_pin") or ""): world
                    for port, world in zip(ports, world_ports)
                    if math.isfinite(world[0]) and math.isfinite(world[1])
                }
                if {"1", "2", "C+", "G-"}.issubset(pin_world):
                    upper = (
                        (pin_world["1"][0] + pin_world["2"][0]) / 2.0,
                        (pin_world["1"][1] + pin_world["2"][1]) / 2.0,
                    )
                    lower = (
                        (pin_world["C+"][0] + pin_world["G-"][0]) / 2.0,
                        (pin_world["C+"][1] + pin_world["G-"][1]) / 2.0,
                    )
                    axis = (upper[0] - lower[0], upper[1] - lower[1])
                    axis_length = math.hypot(axis[0], axis[1])
                    if axis_length > 1e-9:
                        axis = (axis[0] / axis_length, axis[1] / axis_length)
                        top_port_forward = max(
                            (world[0] - center[0]) * axis[0]
                            + (world[1] - center[1]) * axis[1]
                            for world in world_ports
                            if math.isfinite(world[0]) and math.isfinite(world[1])
                        )
                        measured_component_labels = [
                            (distance_value, value, row)
                            for distance_value, value, row in measured_component_labels
                            if (
                                top_port_forward + max(0.5, axis_length * 0.02)
                                < (
                                    (float(row.get("insert_x")) - center[0]) * axis[0]
                                    + (float(row.get("insert_y")) - center[1]) * axis[1]
                                )
                                <= max(component_label_radius * 2.5, axis_length * 2.5)
                                and abs(
                                    (float(row.get("insert_x")) - center[0]) * axis[1]
                                    - (float(row.get("insert_y")) - center[1]) * axis[0]
                                )
                                <= max(8.0, axis_length * 0.45)
                            )
                        ]
            elif numbered_round_contact_array_model:
                pin_world = {
                    int(str(port.get("component_pin") or "")): world
                    for port, world in zip(ports, world_ports)
                    if str(port.get("component_pin") or "").isdigit()
                    and math.isfinite(world[0])
                    and math.isfinite(world[1])
                }
                last_pin = len(pin_world)
                if last_pin >= 8 and {1, 2, last_pin - 1, last_pin}.issubset(pin_world):
                    upper = (
                        (pin_world[1][0] + pin_world[2][0]) / 2.0,
                        (pin_world[1][1] + pin_world[2][1]) / 2.0,
                    )
                    lower = (
                        (pin_world[last_pin - 1][0] + pin_world[last_pin][0]) / 2.0,
                        (pin_world[last_pin - 1][1] + pin_world[last_pin][1]) / 2.0,
                    )
                    axis = (upper[0] - lower[0], upper[1] - lower[1])
                    axis_length = math.hypot(axis[0], axis[1])
                    if axis_length > 1e-9:
                        axis = (axis[0] / axis_length, axis[1] / axis_length)
                        body_half_height = axis_length / 2.0
                        measured_component_labels = [
                            (distance_value, value, row)
                            for distance_value, value, row in measured_component_labels
                            if (
                                body_half_height * 1.05
                                < (
                                    (float(row.get("insert_x")) - center[0]) * axis[0]
                                    + (float(row.get("insert_y")) - center[1]) * axis[1]
                                )
                                <= max(component_label_radius * 2.5, body_half_height * 2.0)
                                and abs(
                                    (float(row.get("insert_x")) - center[0]) * axis[1]
                                    - (float(row.get("insert_y")) - center[1]) * axis[0]
                                )
                                <= max(8.0, body_half_height * 0.5)
                            )
                        ]
            component_labels = sorted(
                measured_component_labels,
                key=lambda item: (item[0], item[1]),
            )
        component_label_limit = component_label_radius * (
            2.5
            if numbered_round_contact_array_model
            else 1.5
            if three_contact_socket_model
            else 1.2
            if vertical_two_port_box_model
            else 1.0
        )
        component_label = (
            component_labels[0]
            if component_labels
            and component_labels[0][0] <= component_label_limit
            else None
        )

        label_pairs: list[tuple[float, int, int]] = []
        for port_index, world in enumerate(world_ports):
            if not math.isfinite(world[0]) or not math.isfinite(world[1]):
                continue
            for text_index, (_, x, y, _) in enumerate(eligible_texts):
                distance = math.hypot(world[0] - x, world[1] - y)
                if distance <= label_radius:
                    label_pairs.append((distance, port_index, text_index))
        assigned_labels: dict[
            int, tuple[float, tuple[str, float, float, dict[str, Any]]]
        ] = {}
        used_texts: set[int] = set()
        for distance, port_index, text_index in sorted(label_pairs):
            if port_index in assigned_labels or text_index in used_texts:
                continue
            assigned_labels[port_index] = (distance, eligible_texts[text_index])
            used_texts.add(text_index)

        assigned_socket_pins: dict[
            int, tuple[float, tuple[str, float, float, dict[str, Any]]]
        ] = {}
        if three_contact_socket_model:
            socket_pairs = sorted(
                (
                    math.hypot(world[0] - x, world[1] - y),
                    port_index,
                    text_index,
                )
                for port_index, world in enumerate(world_ports)
                if math.isfinite(world[0]) and math.isfinite(world[1])
                for text_index, (_, x, y, _) in enumerate(socket_pin_texts)
                if math.hypot(world[0] - x, world[1] - y) <= max(label_radius, 12.0)
            )
            used_socket_texts: set[int] = set()
            for distance, port_index, text_index in socket_pairs:
                if port_index in assigned_socket_pins or text_index in used_socket_texts:
                    continue
                assigned_socket_pins[port_index] = (
                    distance,
                    socket_pin_texts[text_index],
                )
                used_socket_texts.add(text_index)

        assigned_panel_endpoints: dict[
            int, tuple[float, tuple[str, float, float, dict[str, Any]]]
        ] = {}
        used_panel_texts: set[int] = set()
        panel_pairs: list[tuple[float, int, int]] = []
        if communication_panel_model:
            for port_index, (world, outward) in enumerate(
                zip(world_ports, world_outward_directions)
            ):
                if (
                    outward is None
                    or not math.isfinite(world[0])
                    or not math.isfinite(world[1])
                ):
                    continue
                for text_index, (_, x, y, _) in enumerate(panel_endpoint_texts):
                    dx = x - world[0]
                    dy = y - world[1]
                    forward = outward[0] * dx + outward[1] * dy
                    lateral = abs(outward[0] * dy - outward[1] * dx)
                    # Upper labels start beside the short outward stub; lower
                    # labels are drawn as longer upward-rotated strings whose
                    # insertion point sits farther below the cell.
                    max_forward = 22.0 if outward[1] < -0.5 else 5.0
                    if -0.2 <= forward <= max_forward and lateral <= 2.6:
                        panel_pairs.append(
                            (math.hypot(dx, dy), port_index, text_index)
                        )
            for distance, port_index, text_index in sorted(panel_pairs):
                if (
                    port_index in assigned_panel_endpoints
                    or text_index in used_panel_texts
                ):
                    continue
                assigned_panel_endpoints[port_index] = (
                    distance,
                    panel_endpoint_texts[text_index],
                )
                used_panel_texts.add(text_index)

        sheet_lines = [
            row
            for row in line_rows
            if str(row.get("sheet_id") or "") == sheet_id
            and (not file_id or str(row.get("file_id") or "") == file_id)
        ]
        for port_index, (port, world, outward) in enumerate(
            zip(ports, world_ports, world_outward_directions)
        ):
            if not math.isfinite(world[0]) or not math.isfinite(world[1]):
                continue
            attached_lines: list[dict[str, Any]] = []
            for line in sheet_lines:
                try:
                    start = (float(line.get("start_x")), float(line.get("start_y")))
                    end = (float(line.get("end_x")), float(line.get("end_y")))
                except (TypeError, ValueError):
                    continue
                start_distance = math.hypot(world[0] - start[0], world[1] - start[1])
                end_distance = math.hypot(world[0] - end[0], world[1] - end[1])
                if min(start_distance, end_distance) > effective_endpoint_tolerance:
                    continue
                if (
                    terminal_geometry
                    or four_contact_isolated_frame_model
                    or numbered_round_contact_array_model
                ) and outward is not None:
                    away = (
                        (end[0] - start[0], end[1] - start[1])
                        if start_distance <= end_distance
                        else (start[0] - end[0], start[1] - end[1])
                    )
                    away_norm = math.hypot(away[0], away[1])
                    if away_norm <= 1e-12:
                        continue
                    alignment = (
                        outward[0] * away[0] + outward[1] * away[1]
                    ) / away_norm
                    if alignment < 0.5:
                        continue
                attached_lines.append(line)

            # A four-way terminal exposes independent directional contacts.
            # An unwired direction is not a relation and must not become a
            # label-only placeholder that downstream code could misread as a
            # latent attachment.
            if four_contact_terminal_geometry and not attached_lines:
                continue

            panel_binding = assigned_panel_endpoints.get(port_index)
            label_binding = assigned_labels.get(port_index)
            socket_pin_binding = assigned_socket_pins.get(port_index)
            explicit_label = (
                str(port.get("component_pin") or "").strip() or None
                if communication_panel_model
                else str(port.get("component_pin") or "").strip() or None
                if (
                    four_numbered_contact_panel_model
                    or vertical_two_port_box_model
                    or eight_numbered_side_contact_panel_model
                    or horizontal_numbered_two_circle_box_model
                    or selective_component_model
                    or wfs_polarity_model
                    or numbered_round_contact_array_model
                )
                else socket_pin_binding[1][0]
                if socket_pin_binding
                else label_binding[1][0]
                if label_binding
                else None
            )
            label_row = (
                panel_binding[1][3]
                if panel_binding
                else socket_pin_binding[1][3]
                if socket_pin_binding
                else label_binding[1][3]
                if label_binding
                else None
            )
            label_distance_value = (
                panel_binding[0]
                if panel_binding
                else socket_pin_binding[0]
                if socket_pin_binding
                else label_binding[0]
                if label_binding
                else None
            )
            terminal_name = bound_terminal[1] if bound_terminal else None
            terminal_label_row = bound_terminal[2] if bound_terminal else None
            line_handles = sorted(
                {
                    str(row.get("handle") or "").strip()
                    for row in attached_lines
                    if str(row.get("handle") or "").strip()
                }
            )
            line_ids = sorted(
                {
                    str(row.get("line_id") or "").strip()
                    for row in attached_lines
                    if str(row.get("line_id") or "").strip()
                }
            )
            network_ids = sorted(
                {
                    network_id
                    for handle in line_handles
                    for network_id in networks_by_handle.get(handle, set())
                }
            )
            socket_external_binding: tuple[
                float, tuple[str, float, float, dict[str, Any]]
            ] | None = None
            if (
                three_contact_socket_model
                or four_contact_isolated_frame_model
                or two_contact_actuator_model
                or selective_component_model
                or numbered_round_contact_array_model
            ) and (network_ids or attached_lines):
                network_id_set = set(network_ids)
                network_lines = (
                    [
                        row
                        for row in sheet_lines
                        if network_id_set
                        & networks_by_handle.get(
                            str(row.get("handle") or "").strip(), set()
                        )
                    ]
                    if network_id_set
                    else attached_lines
                )
                endpoint_matches: list[
                    tuple[float, float, tuple[str, float, float, dict[str, Any]]]
                ] = []
                endpoint_reach = (
                    14.0
                    if functional_round_contact_array_model
                    else 4.0
                    if two_contact_actuator_model
                    else 8.0
                )
                # Prefer the label beside the line directly attached to this
                # port.  Traverse the wider network only when that local stub
                # has no endpoint label; this prevents a stale/over-unioned
                # network from stealing a sibling socket pin's endpoint.
                line_scopes = [attached_lines]
                if network_lines != attached_lines:
                    line_scopes.append(network_lines)
                for scoped_lines in line_scopes:
                    scoped_matches: list[
                        tuple[float, float, tuple[str, float, float, dict[str, Any]]]
                    ] = []
                    for endpoint in socket_endpoint_texts:
                        value, x, y, endpoint_row = endpoint
                        if (
                            component_label
                            and endpoint_row.get("text_id")
                            == component_label[2].get("text_id")
                        ):
                            continue
                        distances: list[float] = []
                        for line in scoped_lines:
                            try:
                                start = (
                                    float(line.get("start_x")),
                                    float(line.get("start_y")),
                                )
                                end = (
                                    float(line.get("end_x")),
                                    float(line.get("end_y")),
                                )
                            except (TypeError, ValueError):
                                continue
                            distances.append(
                                _point_segment_distance((x, y), start, end)
                            )
                        if distances and min(distances) <= endpoint_reach:
                            scoped_matches.append(
                                (
                                    min(distances),
                                    math.hypot(world[0] - x, world[1] - y),
                                    endpoint,
                                )
                            )
                    if scoped_matches:
                        endpoint_matches = scoped_matches
                        break
                if endpoint_matches:
                    best = min(endpoint_matches, key=lambda item: (item[0], item[1], item[2][0]))
                    socket_external_binding = (best[0], best[2])
                elif four_contact_isolated_frame_model and outward is not None:
                    numeric_matches: list[
                        tuple[float, float, tuple[str, float, float, dict[str, Any]]]
                    ] = []
                    for numeric in eligible_texts:
                        value, x, y, row = numeric
                        if label_row and row.get("text_id") == label_row.get("text_id"):
                            continue
                        forward = outward[0] * (x - world[0]) + outward[1] * (y - world[1])
                        if forward <= 2.0:
                            continue
                        distances = []
                        for line in network_lines:
                            try:
                                start = (float(line.get("start_x")), float(line.get("start_y")))
                                end = (float(line.get("end_x")), float(line.get("end_y")))
                            except (TypeError, ValueError):
                                continue
                            distances.append(_point_segment_distance((x, y), start, end))
                        if distances and min(distances) <= 4.0:
                            numeric_matches.append((min(distances), forward, numeric))
                    if numeric_matches:
                        _, _, numeric = min(
                            numeric_matches, key=lambda item: (item[0], item[1], item[2][0])
                        )
                        component_matches = sorted(
                            (
                                math.hypot(numeric[1] - x, numeric[2] - y),
                                value,
                                row,
                            )
                            for value, x, y, row in external_component_texts
                            if math.hypot(numeric[1] - x, numeric[2] - y) <= 20.0
                        )
                        if component_matches:
                            component_distance, component_name, component_row = component_matches[0]
                            socket_external_binding = (
                                component_distance,
                                (
                                    f"{component_name}-{numeric[0]}",
                                    numeric[1],
                                    numeric[2],
                                    component_row,
                                ),
                            )
            evidence_codes = ["DEFINITION_PORT_WORLD_TRANSFORM"]
            if communication_panel_model:
                evidence_codes.extend(
                    [
                        "REPEATED_COMMUNICATION_PIN_CELL",
                        "NATIVE_PANEL_GROUP_PIN_IDENTITY",
                    ]
                )
                if panel_binding:
                    evidence_codes.append("OUTWARD_EXTERNAL_ENDPOINT_LABEL")
            if explicit_label:
                evidence_codes.append(
                    "INSTANCE_POLARITY_PORT_LABEL"
                    if wfs_polarity_model
                    else "INSTANCE_LOCAL_NUMERIC_PORT_LABEL"
                )
            if (
                named_two_port_strip_model
                or named_two_row_box_model
                or single_row_contact_model
                or four_contact_isolated_frame_model
                or selective_component_model
                or numbered_round_contact_array_model
            ) and component_label:
                evidence_codes.append("INSTANCE_COMPONENT_DESIGNATOR")
            if three_contact_socket_model and component_label and socket_pin_binding:
                evidence_codes.extend(
                    [
                        "INSTANCE_COMPONENT_DESIGNATOR",
                        "INSTANCE_SOCKET_PIN_LABEL",
                    ]
                )
            if socket_external_binding:
                evidence_codes.append("NETWORK_SCOPED_EXTERNAL_ENDPOINT_LABEL")
            if line_handles:
                evidence_codes.append("EXACT_EXTERNAL_LINE_ENDPOINT")
                if (
                    terminal_geometry
                    or four_contact_isolated_frame_model
                    or numbered_round_contact_array_model
                ) and outward is not None:
                    evidence_codes.append("OUTWARD_LINE_ALIGNMENT")
            if network_ids:
                evidence_codes.append("EXTERNAL_NETWORK_MEMBERSHIP")
            terminal_model = (
                "HUMAN_CONFIRMED"
                if policy and policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"
                else "GEOMETRY_HIGH_CONFIDENCE"
                if terminal_geometry
                else None
            )
            terminal_definition_evidence = bool(labelled_terminal)
            terminal_label_evidence = bool(terminal_name)
            terminal_wire_evidence = bool(line_handles)
            terminal_independent_evidence_complete = bool(
                terminal_definition_evidence
                and terminal_label_evidence
                and terminal_wire_evidence
                and not terminal_label_ambiguous
            )
            terminal_missing_evidence: list[str] = []
            if labelled_terminal:
                if not terminal_label_evidence:
                    terminal_missing_evidence.append("UNIQUE_STRUCTURED_DESIGNATOR")
                if not terminal_wire_evidence:
                    terminal_missing_evidence.append("EXTERNAL_WIRE_CONTACT")
            component_port_identity = (
                str(port.get("logical_port_identity") or "").strip() or None
                if communication_panel_model
                else f"{component_label[1]}-{explicit_label}"
                if component_label and explicit_label
                else None
            )
            if (
                named_two_port_strip_model
                or named_two_row_box_model
                or single_row_contact_model
                or four_contact_isolated_frame_model
                or numbered_round_contact_array_model
            ) and component_port_identity:
                evidence_codes.extend(
                    [
                        "COMPONENT_PORT_IDENTITY",
                        "SIDE_SPECIFIC_EXTERNAL_ATTACHMENT",
                    ]
                )
            if three_contact_socket_model and component_port_identity:
                evidence_codes.extend(
                    [
                        "COMPONENT_PORT_IDENTITY",
                        "INDEPENDENT_SOCKET_PORT",
                    ]
                )
            component_mappings = (
                component_mapping_by_port.get((sheet_id, component_port_identity), [])
                if component_port_identity
                else []
            )
            component_endpoints = (
                [panel_binding[1][0]]
                if communication_panel_model and panel_binding
                else [socket_external_binding[1][0]]
                if (
                    three_contact_socket_model
                    or four_contact_isolated_frame_model
                    or two_contact_actuator_model
                    or selective_component_model
                    or numbered_round_contact_array_model
                )
                and socket_external_binding
                else sorted(
                    {
                        str(row.get("right_value") or "").strip()
                        for row in component_mappings
                    }
                    - {""}
                )
            )
            component_pair_ids = sorted(
                {
                    str(row.get("pair_id") or "").strip()
                    for row in component_mappings
                }
                - {""}
            )
            if labelled_terminal and terminal_label_ambiguous:
                status = "TERMINAL_BINDING_AMBIGUOUS"
                confidence = 0.4
            elif terminal_independent_evidence_complete:
                status = "MEASURED_TERMINAL_ATTACHMENT"
                confidence = 0.95 if terminal_model == "HUMAN_CONFIRMED" and network_ids else 0.9 if network_ids else 0.85
            elif labelled_terminal and terminal_label_evidence:
                status = "TERMINAL_LABEL_ONLY_REVIEW"
                confidence = 0.65
            elif labelled_terminal and terminal_wire_evidence:
                status = "TERMINAL_WIRE_ONLY_REVIEW"
                confidence = 0.6
            elif labelled_terminal:
                status = "TERMINAL_GEOMETRY_ONLY_REVIEW"
                confidence = 0.5
            elif (
                communication_panel_model
                and component_endpoints
                and line_handles
            ):
                status = "MEASURED_COMPONENT_PORT_MAPPING"
                confidence = 0.95 if network_ids else 0.92
            elif communication_panel_model and component_endpoints:
                status = "PANEL_ENDPOINT_LABEL_ONLY_REVIEW"
                confidence = 0.7
            elif communication_panel_model and line_handles:
                status = "PANEL_WIRE_ONLY_REVIEW"
                confidence = 0.65
            elif communication_panel_model:
                status = "PANEL_CELL_UNWIRED"
                confidence = 0.5
            elif (
                (
                    named_two_port_strip_model
                    or named_two_row_box_model
                    or single_row_contact_model
                    or selective_component_model
                    or numbered_round_contact_array_model
                )
                and component_port_identity
                and line_handles
            ):
                status = "MEASURED_COMPONENT_PORT_MAPPING"
                confidence = 0.95 if network_ids else 0.92
            elif (
                (
                    three_contact_socket_model
                    or four_contact_isolated_frame_model
                    or selective_component_model
                    or numbered_round_contact_array_model
                )
                and component_port_identity
                and component_endpoints
                and line_handles
            ):
                status = "MEASURED_COMPONENT_PORT_MAPPING"
                confidence = 0.96 if network_ids else 0.92
            elif explicit_label and line_handles:
                status = "MEASURED_EXTERNAL_ATTACHMENT"
                confidence = 0.95 if network_ids else 0.9
            elif component_endpoints:
                status = "MEASURED_COMPONENT_PORT_MAPPING"
                confidence = 0.95
            elif explicit_label:
                status = "LABEL_ONLY_REVIEW"
                confidence = 0.65
            elif line_handles:
                status = "GEOMETRY_ONLY_REVIEW"
                confidence = 0.6
            else:
                status = "UNRESOLVED"
                confidence = 0.0
            candidates.append(
                {
                    "schema_version": "symbol-port-network-candidate-v1",
                    "candidate_id": (
                        f"SPNC:{instance_id or instance_handle}:"
                        f"{explicit_label or port.get('port_id') or port_index}"
                    ),
                    "project_id": instance.get("project_id"),
                    "sheet_id": sheet_id,
                    "file_id": file_id,
                    "symbol_instance_id": instance_id or None,
                    "symbol_instance_handle": instance_handle or None,
                    "definition_name": name,
                    "definition_fingerprint": instance.get("definition_fingerprint"),
                    "binding_status": binding_status,
                    **family,
                    **behavior,
                    "machine_port_id": port.get("port_id"),
                    "explicit_port_label": explicit_label,
                    "terminal_designator": terminal_name,
                    "terminal_model": terminal_model,
                    "terminal_geometry_recognized": terminal_geometry,
                    "terminal_definition_evidence": terminal_definition_evidence,
                    "terminal_label_evidence": terminal_label_evidence,
                    "terminal_wire_evidence": terminal_wire_evidence,
                    "terminal_independent_evidence_complete": terminal_independent_evidence_complete,
                    "terminal_label_ambiguous": terminal_label_ambiguous,
                    "terminal_label_candidates": [
                        {
                            "value": value,
                            "distance": distance,
                            "text_id": row.get("text_id"),
                            "handle": row.get("handle"),
                        }
                        for distance, value, row in distinct_terminal_labels
                    ],
                    "terminal_missing_evidence": terminal_missing_evidence,
                    "terminal_label_handle": terminal_label_row.get("handle") if terminal_label_row else None,
                    "terminal_label_text_id": terminal_label_row.get("text_id") if terminal_label_row else None,
                    "component_designator": (
                        port.get("component_group")
                        if communication_panel_model
                        else component_label[1]
                        if component_label
                        else None
                    ),
                    "component_designator_text_id": component_label[2].get("text_id") if component_label else None,
                    "component_port_identity": component_port_identity,
                    "component_pin": (
                        port.get("component_pin")
                        or explicit_label
                        if (
                            named_two_port_strip_model
                            or named_two_row_box_model
                            or single_row_contact_model
                            or three_contact_socket_model
                            or four_contact_isolated_frame_model
                            or selective_component_model
                            or numbered_round_contact_array_model
                        )
                        else port.get("component_pin")
                    ),
                    "attachment_side": (
                        port.get("attachment_side")
                        or "left"
                        if named_two_port_strip_model and explicit_label == "1"
                        else port.get("attachment_side")
                        or "right"
                        if named_two_port_strip_model and explicit_label == "2"
                        else port.get("attachment_side")
                    ),
                    "component_mapping_external_endpoints": component_endpoints,
                    "component_mapping_external_network_ids": (
                        network_ids
                        if (
                            named_two_port_strip_model
                            or named_two_row_box_model
                            or single_row_contact_model
                            or three_contact_socket_model
                            or four_contact_isolated_frame_model
                            or selective_component_model
                            or numbered_round_contact_array_model
                        )
                        else []
                    ),
                    "component_mapping_pair_ids": component_pair_ids,
                    "cross_page_match_eligible": bool(
                        component_endpoints
                        or (
                            (
                                named_two_port_strip_model
                                or named_two_row_box_model
                                or single_row_contact_model
                                or three_contact_socket_model
                                or four_contact_isolated_frame_model
                                or selective_component_model
                                or numbered_round_contact_array_model
                            )
                            and network_ids
                        )
                    ),
                    "label_handle": label_row.get("handle") if label_row else None,
                    "label_text_id": label_row.get("text_id") if label_row else None,
                    "label_distance": label_distance_value,
                    "local_position": list(port.get("local_position") or []),
                    "world_position": [world[0], world[1], world[2]],
                    "effective_endpoint_tolerance": effective_endpoint_tolerance,
                    "attached_line_ids": line_ids,
                    "attached_line_handles": line_handles,
                    "external_network_ids": network_ids,
                    "relation_kind": (
                        "COMPONENT_PORT_TO_EXTERNAL_NETWORK"
                        if (
                            named_two_port_strip_model
                            or named_two_row_box_model
                            or single_row_contact_model
                            or three_contact_socket_model
                            or four_contact_isolated_frame_model
                            or selective_component_model
                            or numbered_round_contact_array_model
                        )
                        else "PORT_TO_EXTERNAL_NETWORK"
                    ),
                    "status": status,
                    "confidence": confidence,
                    "evidence_codes": evidence_codes,
                    "internal_connectivity_inferred": False,
                    "dynamic_contact_state": "DEFER",
                    "annotation_status": "MACHINE_PROPOSED",
                    "authority": "SHADOW_ONLY",
                    "shadow_only": True,
                    "electrical_union_eligible": False,
                    "critical_issue_eligible": False,
                }
            )
    # A nested row mechanism can be inventoried at the same world transform as
    # its enclosing two-row component.  Keep the first measured parent mapping
    # and suppress only an exactly coincident duplicate; distinct instances,
    # rows, line handles, or networks remain separate.
    deduplicated_candidates: list[dict[str, Any]] = []
    seen_two_row_mappings: set[tuple[Any, ...]] = set()
    for row in candidates:
        if (
            row.get("matched_family_rule_id")
            == "named-two-row-box-four-contact-v1"
            and row.get("relation_kind") == "COMPONENT_PORT_TO_EXTERNAL_NETWORK"
        ):
            duplicate_key = (
                row.get("file_id"),
                row.get("sheet_id"),
                row.get("component_port_identity"),
                tuple(row.get("world_position") or ()),
                tuple(row.get("attached_line_handles") or ()),
                tuple(row.get("external_network_ids") or ()),
            )
            if duplicate_key in seen_two_row_mappings:
                continue
            seen_two_row_mappings.add(duplicate_key)
        deduplicated_candidates.append(row)
    candidates = deduplicated_candidates
    candidates.sort(
        key=lambda row: (
            str(row.get("sheet_id") or ""),
            str(row.get("symbol_instance_id") or ""),
            str(row.get("explicit_port_label") or row.get("machine_port_id") or ""),
        )
    )
    return candidates


def summarize_instance_port_network_candidates(candidates: Any) -> dict[str, Any]:
    """Summarize independent terminal evidence without granting authority."""

    rows = _mapping_rows(candidates)
    status_counts = Counter(str(row.get("status") or "UNRESOLVED") for row in rows)
    family_counts = Counter(str(row.get("family_id") or "UNKNOWN") for row in rows)
    binding_status_counts = Counter(
        str(row.get("binding_status") or "UNVERIFIED") for row in rows
    )
    behavior_mode_counts = Counter(
        str(row.get("behavior_mode") or "UNSPECIFIED") for row in rows
    )
    return {
        "schema_version": "symbol-port-network-candidate-summary-v1",
        "candidate_count": len(rows),
        "measured_external_attachment_count": status_counts.get(
            "MEASURED_EXTERNAL_ATTACHMENT", 0
        ),
        "measured_terminal_attachment_count": status_counts.get(
            "MEASURED_TERMINAL_ATTACHMENT", 0
        ),
        "measured_component_port_mapping_count": status_counts.get(
            "MEASURED_COMPONENT_PORT_MAPPING", 0
        ),
        "terminal_geometry_recognized_count": sum(
            bool(row.get("terminal_geometry_recognized")) for row in rows
        ),
        "independent_evidence_complete_count": sum(
            bool(row.get("terminal_independent_evidence_complete")) for row in rows
        ),
        "ambiguous_binding_count": sum(
            bool(row.get("terminal_label_ambiguous")) for row in rows
        ),
        "terminal_review_only_count": sum(
            str(row.get("status") or "").startswith("TERMINAL_")
            and row.get("status") != "MEASURED_TERMINAL_ATTACHMENT"
            for row in rows
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "binding_status_counts": dict(sorted(binding_status_counts.items())),
        "behavior_mode_counts": dict(sorted(behavior_mode_counts.items())),
        "rejected_fingerprint_mismatch_count": binding_status_counts.get(
            "REJECTED_FINGERPRINT_MISMATCH", 0
        ),
        "geometry_family_match_count": sum(
            str(row.get("family_evidence_source") or "").startswith(
                "MACHINE_GEOMETRY_RULE"
            )
            for row in rows
        ),
        "exact_human_member_count": sum(
            bool(row.get("exact_human_member")) for row in rows
        ),
        "explicit_label_count": sum(bool(row.get("explicit_port_label")) for row in rows),
        "network_bound_count": sum(bool(row.get("external_network_ids")) for row in rows),
        "internal_connectivity_inferred_count": sum(
            bool(row.get("internal_connectivity_inferred")) for row in rows
        ),
        "authority": "SHADOW_ONLY",
        "electrical_union_eligible_count": sum(
            bool(row.get("electrical_union_eligible")) for row in rows
        ),
        "critical_issue_eligible_count": sum(
            bool(row.get("critical_issue_eligible")) for row in rows
        ),
        "primary_engine_unchanged": True,
    }


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "iterrows"):
        return [dict(row) for _, row in value.iterrows()]
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        rows = []
        for item in value:
            if isinstance(item, Mapping):
                rows.append(dict(item))
            elif hasattr(item, "__dataclass_fields__"):
                rows.append(asdict(item))
        return rows
    return []


def _instance_matrix(raw: Any) -> list[list[float]] | None:
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, Mapping):
        return None
    matrix = payload.get("matrix44")
    chain = payload.get("chain")
    if matrix is None and isinstance(chain, Sequence) and chain:
        # Walker chains are ordered outermost -> current instance and each
        # item stores the cumulative world transform at that depth.  The last
        # item therefore owns the nested symbol's actual placement.
        current = chain[-1]
        if isinstance(current, Mapping):
            matrix = current.get("matrix44") or current.get("matrix")
    if not isinstance(matrix, Sequence):
        return None
    try:
        rows = [[float(cell) for cell in row] for row in matrix]
    except (TypeError, ValueError):
        return None
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        return None
    return rows


def _transform_point(
    matrix: list[list[float]], point: tuple[float, float, float]
) -> tuple[float, float, float]:
    x, y, z = point
    if (
        abs(matrix[3][3] - 1.0) <= 1e-9
        and abs(matrix[0][3]) <= 1e-9
        and abs(matrix[1][3]) <= 1e-9
    ):
        return (
            matrix[0][0] * x + matrix[1][0] * y + matrix[2][0] * z + matrix[3][0],
            matrix[0][1] * x + matrix[1][1] * y + matrix[2][1] * z + matrix[3][1],
            matrix[0][2] * x + matrix[1][2] * y + matrix[2][2] * z + matrix[3][2],
        )
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )



def find_block_in_documents(
    definition_names: Sequence[str],
    dxf_paths: Sequence[str | Path],
) -> tuple[Any, str, Path] | None:
    """Return first matching (block, name, path) for any definition name."""

    try:
        import ezdxf
    except Exception:
        return None
    wanted = {str(name).casefold(): str(name) for name in definition_names if str(name).strip()}
    if not wanted:
        return None
    for raw_path in dxf_paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            document = ezdxf.readfile(str(path))
        except Exception:
            continue
        try:
            block_names = {str(block.name): block for block in document.blocks}
        except Exception:
            continue
        for key, original in wanted.items():
            for block_name, block in block_names.items():
                if str(block_name).casefold() == key:
                    try:
                        if bool(getattr(block, "is_any_layout", False)):
                            continue
                    except Exception:
                        pass
                    return block, original, path
    return None


def propose_ports_for_queue_row(
    row: Mapping[str, Any],
    dxf_paths: Sequence[str | Path],
    *,
    max_ports: int = 4,
) -> SymbolPortProposal:
    names = row.get("definition_names") or []
    if isinstance(names, str):
        names = [part for part in names.split("|") if part]
    names = [str(name) for name in names if str(name).strip()]
    fingerprint = str(row.get("definition_fingerprint") or "") or None
    match = find_block_in_documents(names, dxf_paths)
    if match is None:
        return SymbolPortProposal(
            definition_name=names[0] if names else "UNKNOWN",
            definition_fingerprint=fingerprint,
            source_dxf=None,
            ports=(),
            method="free_endpoint_extremes_v1",
            status="BLOCK_NOT_FOUND",
            notes=("No matching block definition found in provided DXF set.",),
            geometry_summary={},
        )
    block, name, path = match
    return propose_ports_from_block(
        block,
        definition_name=name,
        definition_fingerprint=fingerprint,
        source_dxf=path,
        max_ports=max_ports,
    )


def apply_proposals_to_review_document(
    document: Mapping[str, Any],
    proposals_by_fingerprint: Mapping[str, SymbolPortProposal],
) -> dict[str, Any]:
    """Inject MACHINE_PROPOSED ports into a review document without authority."""

    payload = json.loads(json.dumps(document))  # deep copy via JSON
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        return payload
    for symbol in symbols:
        if not isinstance(symbol, dict):
            continue
        fingerprint = str(symbol.get("fingerprint") or "")
        proposal = proposals_by_fingerprint.get(fingerprint)
        policy = human_symbol_port_policy(fingerprint)
        if proposal is None:
            continue
        if policy is not None and policy["mode"] in {
            "IGNORE_ELECTRICAL",
            "TABLE_CONTAINER_NO_DIRECT_PORTS",
        }:
            symbol["ports"] = []
            symbol["internal_connectivity_groups"] = []
            continue
        if not proposal.ports:
            continue
        source_id = f"{SOURCE_KIND}:{proposal.definition_name}"
        existing_sources = symbol.get("sources")
        if not isinstance(existing_sources, list):
            existing_sources = []
        if not any(
            isinstance(item, dict) and item.get("source_id") == source_id
            for item in existing_sources
        ):
            existing_sources.append(
                {
                    "source_id": source_id,
                    "source_kind": SOURCE_KIND,
                    "locator": proposal.source_dxf or proposal.definition_name,
                    "project_id": None,
                    "held_out": False,
                }
            )
        symbol["sources"] = existing_sources
        symbol["ports"] = [port.to_review_port() for port in proposal.ports]
        # Keep symbol-level status non-authoritative.
        symbol["annotation_status"] = "MACHINE_PROPOSED"
        symbol["registry_status"] = "UNKNOWN"
        symbol["critical_issue_eligible"] = False
        # A two-port geometry alone cannot establish conductivity. Human review
        # can explicitly suppress the old review-only series placeholder.
        if (
            len(proposal.ports) == 2
            and not (
                policy is not None
                and policy["mode"] in {
                    "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
                    "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
                }
            )
        ):
            symbol["internal_connectivity_groups"] = [
                {
                    "group_id": "MP_SERIES",
                    "port_ids": [proposal.ports[0].port_id, proposal.ports[1].port_id],
                    "state": "POSSIBLE",
                    "annotation_status": "MACHINE_PROPOSED",
                    "source_ids": [source_id],
                }
            ]
        else:
            symbol["internal_connectivity_groups"] = []
        review = symbol.get("review")
        if not isinstance(review, dict):
            review = {}
        # Pending review metadata must remain empty per review safety contract.
        # Machine notes live on workflow / proposal artifacts, not reviewer fields.
        review.update(
            {
                "status": "PENDING_HUMAN_REVIEW",
                "reviewer": None,
                "reviewed_at": None,
                "evidence_source_ids": [],
                "notes": None,
            }
        )
        symbol["review"] = review

    workflow = payload.get("review_workflow")
    if isinstance(workflow, dict):
        workflow["document_status"] = "PENDING_HUMAN_REVIEW"
        notes = workflow.get("notes")
        prefix = "Contains MACHINE_PROPOSED ports from geometry; not human-confirmed."
        workflow["notes"] = prefix if not notes else f"{notes} | {prefix}"
    return payload


def write_human_review_checklist(
    *,
    proposals: Sequence[Mapping[str, Any] | SymbolPortProposal],
    draft_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Write a human checklist for MACHINE_PROPOSED drafts (never auto-confirm)."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    draft_display = str(draft_path)
    lines = [
        "# Human Port Review Checklist (Machine Draft)",
        "",
        "These ports are **MACHINE_PROPOSED** from DXF block geometry.",
        "They are **not** human-confirmed and **cannot** flip `primary_engine`.",
        "",
        f"Draft document: `{draft_display}`",
        "",
        "## How to confirm a symbol",
        "1. Open the matching DWG/DXF block and verify terminal locations.",
        "2. Edit the draft JSON for that symbol:",
        "   - set each accepted port `annotation_status` to `HUMAN_CONFIRMED`",
        "   - set symbol `annotation_status` to `HUMAN_CONFIRMED`",
        "   - set `registry_status` to `REGISTERED` only if identity is trusted",
        "   - set connectivity `state` to `ASSERTED` only with human confirmation",
        "   - fill `review.reviewer`, `review.reviewed_at` (ISO8601), `review.status=HUMAN_CONFIRMED`",
        "   - set document `review_workflow.document_status=REVIEW_COMPLETE`",
        "3. Run: `dwg-audit validate-symbol-review -i <edited.json>`",
        "4. Run: `dwg-audit promote-symbol-review -i <edited.json> -o configs/approved_symbol_library.json`",
        "",
        "## Proposed symbols",
        "",
    ]
    for item in proposals:
        row = item.to_dict() if isinstance(item, SymbolPortProposal) else dict(item)
        name = str(row.get("definition_name") or "UNKNOWN")
        fingerprint = str(row.get("definition_fingerprint") or "")
        short_fp = fingerprint[:16] if fingerprint else "no-fingerprint"
        status = str(row.get("status") or "UNKNOWN")
        lines.append(f"### {name} (`{short_fp}`)")
        lines.append(f"- status: `{status}`")
        if row.get("source_dxf"):
            lines.append(f"- source DXF: `{row.get('source_dxf')}`")
        if row.get("method"):
            lines.append(f"- method: `{row.get('method')}`")
        notes = row.get("notes") or []
        if notes:
            if isinstance(notes, str):
                notes_text = notes
            else:
                notes_text = "; ".join(str(note) for note in notes if str(note).strip())
            if notes_text:
                lines.append(f"- notes: {notes_text}")
        ports = list(row.get("ports") or [])
        if ports:
            lines.append("- ports:")
            for port in ports:
                pos = port.get("local_position") or []
                direction = port.get("outward_direction") or []
                conf = port.get("confidence")
                codes = port.get("evidence_codes") or []
                pos_text = (
                    f"({float(pos[0]):.3f},{float(pos[1]):.3f})"
                    if len(pos) >= 2
                    else str(pos)
                )
                dir_text = (
                    f"({float(direction[0]):.2f},{float(direction[1]):.2f})"
                    if len(direction) >= 2
                    else str(direction)
                )
                conf_text = f"{float(conf):.2f}" if conf is not None else "n/a"
                code_text = ",".join(str(code) for code in codes) if codes else ""
                lines.append(
                    f"  - `{port.get('port_id')}` pos={pos_text} dir={dir_text} "
                    f"conf={conf_text}"
                    + (f" codes={code_text}" if code_text else "")
                )
            if len(ports) == 2:
                lines.append(
                    "- connectivity draft: `MP_SERIES` state=`POSSIBLE` "
                    f"ports={[port.get('port_id') for port in ports]}"
                )
        lines.append("- human decision: [ ] confirm  [ ] edit  [ ] reject")
        lines.append("")

    lines.extend(
        [
            "## Gate reminder",
            "- MACHINE_PROPOSED drafts never authorize critical issues.",
            "- Held-out human gold + product approval remain required before "
            "`primary_engine` can leave `legacy`.",
            "",
        ]
    )
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def write_machine_proposed_review_pack(
    *,
    review_document_path: str | Path,
    dxf_paths: Sequence[str | Path],
    output_dir: str | Path,
    queue_rows: Sequence[Mapping[str, Any]] | None = None,
    max_ports: int = 4,
) -> dict[str, Any]:
    """Load a Top-N review template, propose ports from DXFs, write draft pack."""

    source_path = Path(review_document_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    document = json.loads(source_path.read_text(encoding="utf-8"))

    rows = list(queue_rows or [])
    if not rows:
        for symbol in document.get("symbols") or []:
            if isinstance(symbol, dict):
                rows.append(
                    {
                        "definition_fingerprint": symbol.get("fingerprint"),
                        "definition_names": symbol.get("definition_names") or [],
                    }
                )

    proposals: dict[str, SymbolPortProposal] = {}
    proposal_rows: list[dict[str, Any]] = []
    for row in rows:
        proposal = propose_ports_for_queue_row(row, dxf_paths, max_ports=max_ports)
        fingerprint = str(row.get("definition_fingerprint") or proposal.definition_fingerprint or "")
        if fingerprint:
            proposals[fingerprint] = proposal
        proposal_rows.append(proposal.to_dict())

    drafted = apply_proposals_to_review_document(document, proposals)
    draft_path = output / "symbol_review_machine_proposed.json"
    draft_path.write_text(
        json.dumps(drafted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    proposals_path = output / "symbol_port_proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "schema_version": PROPOSAL_SCHEMA_VERSION,
                "proposal_count": len(proposal_rows),
                "proposed_with_ports": sum(1 for row in proposal_rows if row.get("ports")),
                "block_not_found": sum(
                    1 for row in proposal_rows if row.get("status") == "BLOCK_NOT_FOUND"
                ),
                "proposals": proposal_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": "symbol-port-proposal-summary-v1",
        "input_review_document": str(source_path),
        "draft_review_document": str(draft_path),
        "proposal_count": len(proposal_rows),
        "proposed_with_ports": sum(1 for row in proposal_rows if row.get("ports")),
        "block_not_found": sum(
            1 for row in proposal_rows if row.get("status") == "BLOCK_NOT_FOUND"
        ),
        "total_ports": sum(len(row.get("ports") or []) for row in proposal_rows),
        "authority": "MACHINE_PROPOSED_ONLY",
        "human_confirmed": False,
        "promotion_ready": False,
        "critical_issue_eligible_count": 0,
        "primary_engine_unchanged": True,
    }
    summary_path = output / "symbol_port_proposal_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    checklist_path = write_human_review_checklist(
        proposals=proposal_rows,
        draft_path=draft_path,
        output_path=output / "HUMAN_REVIEW_CHECKLIST.md",
    )
    return {
        "summary": summary,
        "draft_path": draft_path,
        "proposals_path": proposals_path,
        "summary_path": summary_path,
        "checklist_path": checklist_path,
        "proposals": proposals,
        "document": drafted,
    }


__all__ = [
    "PROPOSAL_SCHEMA_VERSION",
    "ProposedPort",
    "SymbolPortProposal",
    "apply_human_symbol_policy_to_proposal_row",
    "apply_proposals_to_review_document",
    "build_instance_port_network_candidates",
    "classify_definition_family",
    "evaluate_symbol_behavior",
    "extract_block_segments",
    "extract_block_shape_features",
    "find_block_in_documents",
    "human_symbol_port_policy",
    "is_high_confidence_terminal_geometry",
    "propose_ports_for_queue_row",
    "propose_ports_from_block",
    "propose_ports_from_segments",
    "summarize_instance_port_network_candidates",
    "write_human_review_checklist",
    "write_machine_proposed_review_pack",
]
