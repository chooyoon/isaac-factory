"""Collision-group authoring.

Four named ``UsdPhysics.CollisionGroup`` prims at ``/World/Collisions``:

  * ``Environment`` — floor, cage walls, pedestal, work fixture
  * ``Machinery``   — conveyor belt + rails
  * ``Consumable``  — pegs, housings, trays
  * ``Robot``       — UR10e links (populated in Phase 3A)

Collision matrix (Phase B starting point):

  * No ``filteredGroups`` relationships authored → every group collides
    with every other group **explicitly** (matrix is permissive but the
    groups are explicit entities, not defaults).
  * Exclusion authoring deferred to Phase 3A when the robot lands and
    we need ``Robot ↮ Cage`` (workspace-safety filter) and similar.

Group membership is authored via the collection
``collection:colliders:includes`` relationship on each
``UsdPhysics.CollisionGroup`` — that is the canonical USD-physics
mechanism (Isaac Sim 5 uses it without translation).
"""

from __future__ import annotations

from pxr import Sdf, Usd, UsdPhysics


COLLISIONS_ROOT = Sdf.Path("/World/Collisions")

ENVIRONMENT_GROUP_PATH = COLLISIONS_ROOT.AppendChild("Environment")
MACHINERY_GROUP_PATH   = COLLISIONS_ROOT.AppendChild("Machinery")
CONSUMABLE_GROUP_PATH  = COLLISIONS_ROOT.AppendChild("Consumable")
ROBOT_GROUP_PATH       = COLLISIONS_ROOT.AppendChild("Robot")


_GROUP_PATHS = (
    ENVIRONMENT_GROUP_PATH,
    MACHINERY_GROUP_PATH,
    CONSUMABLE_GROUP_PATH,
    ROBOT_GROUP_PATH,
)


def author_collision_groups(stage: Usd.Stage) -> None:
    """Define the four named collision groups under ``/World/Collisions``.

    Idempotent. No ``filteredGroups`` relationships are authored — the
    matrix is permissive-but-explicit.
    """
    from pxr import UsdGeom
    UsdGeom.Scope.Define(stage, COLLISIONS_ROOT)
    for path in _GROUP_PATHS:
        UsdPhysics.CollisionGroup.Define(stage, path)


def add_member(stage: Usd.Stage, group_path: Sdf.Path, collider_path: Sdf.Path) -> None:
    """Add a collider prim to a collision group's ``includes`` relation.

    Idempotent — duplicate additions of the same path are coalesced by
    the USD primSpec relation list-op machinery.
    """
    group_prim = stage.GetPrimAtPath(group_path)
    if not group_prim or not group_prim.IsValid():
        raise RuntimeError(f"CollisionGroup not found: {group_path}")
    group = UsdPhysics.CollisionGroup(group_prim)
    coll = group.GetCollidersCollectionAPI()
    coll.CreateIncludesRel().AddTarget(str(collider_path))
