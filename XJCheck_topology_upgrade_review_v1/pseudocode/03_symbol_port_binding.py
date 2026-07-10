"""Pseudocode for symbol bootstrap, instance resolution and port binding."""


def bootstrap_symbol_inventory(projects, primitive_store):
    inventory = {}
    for project in projects:
        for block in primitive_store.blocks(project):
            definition = primitive_store.block_definition(block.definition_id)
            key = stable_definition_hash(definition)
            record = inventory.setdefault(key, new_inventory_record(definition))
            record.block_names.add(block.name)
            record.instance_count += 1
            record.projects.add(project.project_id)
            record.pages.add(block.sheet_id)
            record.transforms.add(normalize_transform(block.transform))
            record.attribute_tags.update(block.attribute_tags)
            record.touch_clusters.extend(infer_external_touch_clusters(block, primitive_store))
            record.geometry_fingerprint = geometry_fingerprint(definition)
    return rank_for_human_review(inventory)


def resolve_symbol_instance(block, registry):
    candidates = registry.lookup(
        block_name=block.name,
        definition_hash=block.definition_hash,
        geometry_fingerprint=block.geometry_fingerprint,
        attribute_tags=block.attribute_tags,
    )
    if not candidates:
        return UnknownSymbolInstance.from_block(block)

    ranked = rank_symbol_families(block, candidates)
    best = ranked[0]
    if best.score < registry.minimum_family_score:
        return UnknownSymbolInstance.from_block(block, alternatives=ranked[:5])
    return SymbolInstance(
        instance_id=new_id("SI"),
        family_id=best.family.family_id,
        source_block_id=block.block_id,
        family_confidence=best.score,
        verification_status=best.family.verification.status,
        alternatives=ranked[1:5],
    )


def transform_ports(symbol_instance, family, block_transform):
    ports = []
    for port_template in family.ports:
        world_xy = apply_insert_transform(
            local_xy=port_template.local_position,
            insertion=block_transform.insertion,
            rotation=block_transform.rotation,
            scale_x=block_transform.scale_x,
            scale_y=block_transform.scale_y,
            mirrored=block_transform.mirrored,
        )
        world_direction = transform_direction(port_template.direction, block_transform)
        ports.append(SymbolPort.from_template(symbol_instance, port_template, world_xy, world_direction))
    return ports


def build_port_binding_candidates(symbol_ports, geometry_graph, config):
    candidates = []
    for port in symbol_ports:
        nearby = geometry_graph.open_geometry_nodes_near(port.xy, port.snap_tolerance(config))
        for node in nearby:
            candidates.append(
                PortBindingCandidate(
                    candidate_id=new_id("PB"),
                    port_id=port.port_id,
                    geometry_node_id=node.node_id,
                    features={
                        "distance": distance(port.xy, node.xy),
                        "direction_alignment": direction_alignment(port.direction, node.tangent),
                        "same_medium": medium_compatible(port.medium, node.medium),
                        "family_verified": port.symbol.verification_status == "human_verified",
                        "repeated_instance_pattern": repeated_binding_support(port, node),
                    },
                )
            )
    return candidates


def bind_ports(candidates, verified_symbol_rules, model=None):
    decisions = []
    for c in candidates:
        if verified_symbol_rules.forbid(c):
            decisions.append(reject(c, "VERIFIED_SYMBOL_RULE_FORBIDS_BINDING"))
            continue
        if verified_symbol_rules.require(c):
            decisions.append(assert_relation(c, "VERIFIED_SYMBOL_PORT_TOUCH"))
            continue

        score = deterministic_port_score(c.features)
        if model is not None:
            score = calibrated_fusion(score, model.predict_proba(c.features))
        decisions.append(possible(c, score, "PORT_BINDING_REQUIRES_GLOBAL_RESOLUTION"))
    return decisions


def build_electrical_networks(geometry_graph, symbols, selected_port_bindings):
    net_graph = graph_from_asserted_geometry(geometry_graph)
    for binding in selected_port_bindings:
        net_graph.attach_symbol_port(binding.port_id, binding.geometry_node_id)

    for symbol in symbols:
        family = symbol.family
        for relation in family.internal_connections:
            if relation.behavior == "permanent_connected":
                net_graph.connect_ports(symbol.port(relation.from_port), symbol.port(relation.to_port))
            elif relation.behavior in {"isolated", "visual_only"}:
                pass
            else:
                net_graph.add_conditional_internal_relation(symbol, relation)
    return connected_components_with_provenance(net_graph)
