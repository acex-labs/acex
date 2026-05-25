from fastapi import APIRouter
from acex.constants import BASE_URL


def create_router(automation_engine):
    if not hasattr(automation_engine, "physical_manager"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/physical", tags=["Physical"])
    pm = automation_engine.physical_manager

    # Site overview (canvas data)
    router.add_api_route("/sites/{site_id}/overview", pm.get_site_overview, methods=["GET"])
    router.add_api_route("/sites/{site_id}/ports", pm.list_all_ports_for_site, methods=["GET"])

    # Site floor plan layout
    router.add_api_route("/sites/{site_id}/layout", pm.get_site_layout, methods=["GET"])
    router.add_api_route("/sites/{site_id}/layout", pm.set_site_layout, methods=["PUT"])
    router.add_api_route("/sites/{site_id}/layout", pm.delete_site_layout, methods=["DELETE"])

    # Buildings
    router.add_api_route("/sites/{site_id}/buildings", pm.list_buildings, methods=["GET"])
    router.add_api_route("/buildings", pm.create_building, methods=["POST"])
    router.add_api_route("/buildings/{building_id:int}", pm.get_building, methods=["GET"])
    router.add_api_route("/buildings/{building_id:int}", pm.update_building, methods=["PATCH"])
    router.add_api_route("/buildings/{building_id:int}", pm.delete_building, methods=["DELETE"])

    # Rooms
    router.add_api_route("/sites/{site_id}/rooms", pm.list_rooms, methods=["GET"])
    router.add_api_route("/rooms", pm.create_room, methods=["POST"])
    router.add_api_route("/rooms/{room_id:int}", pm.get_room, methods=["GET"])
    router.add_api_route("/rooms/{room_id:int}", pm.update_room, methods=["PATCH"])
    router.add_api_route("/rooms/{room_id:int}", pm.delete_room, methods=["DELETE"])

    # Racks
    router.add_api_route("/rooms/{room_id}/racks", pm.list_racks, methods=["GET"])
    router.add_api_route("/racks", pm.create_rack, methods=["POST"])
    router.add_api_route("/racks/{rack_id:int}", pm.get_rack, methods=["GET"])
    router.add_api_route("/racks/{rack_id:int}", pm.update_rack, methods=["PATCH"])
    router.add_api_route("/racks/{rack_id:int}", pm.delete_rack, methods=["DELETE"])

    # Panels
    router.add_api_route("/racks/{rack_id}/panels", pm.list_panels, methods=["GET"])
    router.add_api_route("/panels", pm.create_panel, methods=["POST"])
    router.add_api_route("/panels/{panel_id:int}", pm.get_panel, methods=["GET"])
    router.add_api_route("/panels/{panel_id:int}", pm.delete_panel, methods=["DELETE"])

    # Panel ports
    router.add_api_route("/panels/{panel_id}/ports", pm.list_panel_ports, methods=["GET"])
    router.add_api_route("/ports/{port_id}", pm.update_panel_port, methods=["PATCH"])

    # Fiber trunks
    router.add_api_route("/panels/{panel_id}/fiber-trunks", pm.list_fiber_trunks_by_panel, methods=["GET"])
    router.add_api_route("/fiber-trunks", pm.create_fiber_trunk, methods=["POST"])
    router.add_api_route("/fiber-trunks/{trunk_id:int}", pm.get_fiber_trunk, methods=["GET"])
    router.add_api_route("/fiber-trunks/{trunk_id:int}", pm.delete_fiber_trunk, methods=["DELETE"])

    # Fibers
    router.add_api_route("/fiber-trunks/{trunk_id}/fibers", pm.list_fibers, methods=["GET"])

    # Fiber terminations
    router.add_api_route("/fiber-trunks/{trunk_id}/terminations", pm.list_fiber_terminations, methods=["GET"])
    router.add_api_route("/fiber-terminations/bulk", pm.create_bulk_terminations, methods=["POST"])
    router.add_api_route("/fiber-terminations", pm.create_fiber_termination, methods=["POST"])
    router.add_api_route("/fiber-terminations/{term_id:int}", pm.delete_fiber_termination, methods=["DELETE"])

    # Cross-connections
    router.add_api_route("/panels/{panel_id}/cross-connections", pm.list_cross_connections_by_panel, methods=["GET"])
    router.add_api_route("/cross-connections", pm.create_cross_connection, methods=["POST"])
    router.add_api_route("/cross-connections/{cc_id:int}", pm.delete_cross_connection, methods=["DELETE"])

    # Patch (duplex or simplex, creates 1-2 linked CCs atomically)
    router.add_api_route("/patches", pm.create_patch, methods=["POST"])

    # Trace
    router.add_api_route("/trace/{port_id}", pm.trace, methods=["GET"])

    return router
