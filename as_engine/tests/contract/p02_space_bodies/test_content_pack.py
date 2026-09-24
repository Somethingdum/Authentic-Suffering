"""Content packs (P2). Rules CNT-00..14, LORE-01 (content/pack.py).

The bad packs are built in tmp_path from small Python dicts so every case shows, in one place,
exactly which field breaks which rule. Each case asserts the rule's code fires on the right file
and that the core pack alone stays clean.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from as_engine.content.pack import compile_packs, load_canon, load_pack
from as_engine.content.safety import MINOR_UNSAFE_TERMS
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.testing.scenario import StubSpec, stub_dossier

pytestmark = pytest.mark.phase(2)


# --------------------------------------------------------------------------- builders
def _raw(core_pack_dir: Path, rel: str):
    return yaml.safe_load((core_pack_dir / rel).read_text(encoding="utf-8"))


def _person(pid="tester", name="Hal Brenner", age=40, **over):
    d = stub_dossier(pid, StubSpec(name=name, age=age, sex="male", occupation="welder"))
    d["id"] = pid
    d["generation"] = "authored"
    d["tags"] = []
    for k, v in over.items():
        d[k] = v
    return d


def make_pack(tmp: Path, pack_id: str, files: dict[str, object], *, depends_on=("core",),
              overrides=()) -> Path:
    """Write a pack: files maps a relative path to a YAML-able object or to raw text."""
    root = tmp / pack_id
    root.mkdir(parents=True)
    manifest = {"schema": "as.pack.v1", "id": pack_id, "name": f"Test pack {pack_id}", "version": "1.0.0",
                "description": "Built by a contract test.", "depends_on": list(depends_on)}
    if overrides:
        manifest["overrides"] = list(overrides)
    (root / "pack.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    for rel, obj in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(obj if isinstance(obj, str) else yaml.safe_dump(obj, sort_keys=False, allow_unicode=True),
                     encoding="utf-8")
    return root


def lore_md(lore_id: str, truth: str, beliefs=None, body: str = "") -> str:
    fm = {"schema": "as.lore.v1", "id": lore_id, "title": lore_id.replace("_", " ").title(), "kind": "rumour",
          "truth": truth,
          "beliefs": beliefs if beliefs is not None else [{"held_by": "common", "text": "People say the water tower is haunted.", "confidence": 1}]}
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n" + body


def issues_for(core_pack_dir, pack_root):
    canon, issues = load_canon([core_pack_dir, pack_root])
    return canon, issues


def codes(issues, severity="error"):
    return sorted({i.code for i in issues if i.severity == severity})


# --------------------------------------------------------------------------- core
def test_core_pack_is_clean(core_pack_dir):
    """P2 gate: the core pack loads with no issue at all (errors or warnings)."""
    _, issues = load_canon([core_pack_dir])
    assert issues == [], "\n".join(f"{i.code} {i.file}: {i.message}" for i in issues)


def test_core_pack_contents(canon):
    """09 §2: ten people and three playable characters, with the canon infected set."""
    assert len(canon.all("actor")) == 10 and len(canon.all("pc")) == 3
    assert {r.rsplit("/", 1)[1] for r in canon.refs("pc")} == {"addison_flores", "owen_marsh", "ruth_castillo"}
    assert {r.rsplit("/", 1)[1] for r in canon.refs("infected")} == {
        "ZOMBIE_ARCHETYPE_SHAMBLER01", "ZOMBIE_ARCHETYPE_CRAWLER01", "ZOMBIE_VARIANT_ID_RUNNER01", "ZOMBIE_VARIANT_ID_LURKER01"}
    assert {r.rsplit("/", 1)[1] for r in canon.refs("pathway")} == {"wet", "cold_start", "air", "lurker_deep"}
    assert len(canon.all("lore")) >= 14 and len(canon.all("cue")) >= 50 and len(canon.all("affordance")) >= 60


def test_canon_lookup_helpers(canon):
    mara = canon.get("core:actor/mara_voss")
    assert mara.identity.name.startswith("Mara")
    assert canon.find("infected", "ZOMBIE_ARCHETYPE_SHAMBLER01").name
    assert canon.find("cue", "loud_noise").description
    assert canon.has("core:item/glock_19") and not canon.has("core:item/glock_190")
    with pytest.raises(KeyError):
        canon.find("cue", "no_such_cue")


def test_lore_body_is_kept_as_depth_text(canon):
    """A lore .md file's markdown body is stored on the record (LoreEntry.body)."""
    fall = canon.get("core:lore/the_fall")
    assert fall.truth and fall.beliefs
    assert fall.body and len(fall.body) > 50


def test_cheat_pack_needs_core_and_carries_fredrick(core_pack_dir, cheat_pack_dir):
    canon, issues = load_canon([cheat_pack_dir, core_pack_dir])  # order given does not matter
    assert [i for i in issues if i.severity == "error"] == []
    assert [p.manifest.id for p in canon.packs] == ["core", "cheat_admin"]  # dependency order
    assert canon.get("cheat_admin:actor/fredrick").generation == "cheat"
    _, alone = load_canon([cheat_pack_dir])
    assert any(i.code == "CNT-04" and i.file == "pack.yaml" for i in alone)


# --------------------------------------------------------------------------- each rule
def test_cnt00_bad_yaml_and_wrong_schema(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "badyaml", {
        "items/broken.yaml": "- id: thing\n  name: [unclosed\n",
        "laws/not_a_law.yaml": [{"schema": "as.item.v1", "id": "stray"}],
    })
    _, issues = issues_for(core_pack_dir, root)
    bad = {(i.code, i.file) for i in issues if i.severity == "error"}
    assert ("CNT-00", "items/broken.yaml") in bad and ("CNT-00", "laws/not_a_law.yaml") in bad


def test_cnt00_duplicate_keys_are_refused(tmp_path, core_pack_dir):
    """YAML silently keeps the last of two equal keys; the loader refuses the file instead."""
    root = make_pack(tmp_path, "dupkey", {
        "items/twice.yaml": "- schema: as.item.v1\n  id: rope\n  name: Rope\n  name: Cord\n  plural: ropes\n"
                            "  kind: tool\n  mass_g: 800\n  bulk: 2\n  description: Ten metres of rope.\n",
    })
    canon, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-00")
    assert hit.file == "items/twice.yaml" and "name" in hit.message
    assert not canon.has("dupkey:item/rope")


def test_cnt01_tooling_exhaust(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "exhaust", {
        "lore/tower.md": lore_md("water_tower", "The tower is empty and structurally sound.", body="TODO: write the rest."),
    })
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-01" and i.file == "lore/tower.md" for i in issues)


def test_cnt02_boilerplate_plus_an_index(tmp_path, core_pack_dir):
    def quirk(n, times):
        return {"schema": "as.quirk.v1", "id": f"TEST_RATTLE_{n:02d}", "applies_to": ["ZOMBIE_ARCHETYPE_SHAMBLER01"],
                "text": f"Rattles a door handle {times} times before it gives up and wanders off.",
                "observable_tell": f"The handle rattles {times} times, then stops."}
    root = make_pack(tmp_path, "boiler", {"infected/rattle.yaml": [quirk(1, 3), quirk(2, 4), quirk(3, 5)]})
    _, issues = issues_for(core_pack_dir, root)
    hits = [i for i in issues if i.code == "CNT-02"]
    assert len(hits) == 2, "every record after the first is an error"
    assert all("TEST_RATTLE_01" not in i.message.split(" is the same")[0] for i in hits)


def test_cnt02_does_not_touch_items(tmp_path, core_pack_dir):
    """Items differing only by numbers are normal (a 15-round and a 17-round magazine)."""
    base = {"schema": "as.item.v1", "name": "Box of nails", "plural": "boxes of nails", "kind": "misc",
            "mass_g": 500, "bulk": 1, "description": "A box of 100 nails."}
    root = make_pack(tmp_path, "nails", {"items/nails.yaml": [dict(base, id="nails_100"),
                                                              dict(base, id="nails_200", description="A box of 200 nails.")]})
    _, issues = issues_for(core_pack_dir, root)
    assert not [i for i in issues if i.code == "CNT-02"]


def test_cnt03_duplicate_ids_need_overrides(tmp_path, core_pack_dir):
    glock = next(r for r in _raw(core_pack_dir, "items/weapons.yaml") if r["id"] == "glock_19")
    changed = dict(glock, description="A Glock 19 with a cracked frame; it still fires.")
    root = make_pack(tmp_path, "dupe", {"items/guns.yaml": [changed]})
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-03" and i.file == "items/guns.yaml" for i in issues)

    root2 = make_pack(tmp_path / "b", "house_rules", {"items/guns.yaml": [changed]}, overrides=["core:item/glock_19"])
    canon, issues2 = issues_for(core_pack_dir, root2)
    assert not [i for i in issues2 if i.severity == "error"]
    assert canon.get("core:item/glock_19").description.startswith("A Glock 19 with a cracked frame")
    assert not canon.has("house_rules:item/glock_19"), "an override keeps the earlier ref"


def test_cnt04_unresolved_ref_with_suggestion(tmp_path, core_pack_dir):
    person = _person()
    person["social"]["relations"] = [{"target": "core:actor/eli_vos", "kind": "friend",
                                      "history": "Taught the boy to fish in the spring."}]
    root = make_pack(tmp_path, "badref", {"actors/hal.yaml": person})
    _, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-04")
    assert hit.file == "actors/hal.yaml" and hit.field == "social.relations[0].target"
    assert "Did you mean 'core:actor/eli_voss'?" in hit.message
    assert hit.message.startswith("actors/hal.yaml: ")


def test_cnt04_missing_dependency(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "orphan", {}, depends_on=("ghost_pack",))
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-04" and i.file == "pack.yaml" and "ghost_pack" in i.message for i in issues)


def _affordance(core_pack_dir, **over):
    a = copy.deepcopy(next(r for r in _raw(core_pack_dir, "affordances/movement.yaml") if r["id"] == "move_to_anchor"))
    a["id"] = "test_move"
    a.update(over)
    return a


def test_cnt05_unknown_cue(tmp_path, core_pack_dir):
    a = _affordance(core_pack_dir, requires={"mobile": True, "belief_cues": ["no_such_cue"]})
    root = make_pack(tmp_path, "cue", {"affordances/test.yaml": [a]})
    _, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-05")
    assert hit.field == "requires.belief_cues[0]" and "no_such_cue" in hit.message


def test_cnt05_trained_response_cue(tmp_path, core_pack_dir):
    person = _person()
    person["capability"]["trained_responses"] = [{"cue": "gunshot_closee", "verb": "take_cover"}]
    root = make_pack(tmp_path, "cue2", {"actors/hal.yaml": person})
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-05" and i.field == "capability.trained_responses[0].cue" for i in issues)


def test_cnt06_unknown_effect(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "effect", {"affordances/test.yaml": [_affordance(core_pack_dir, id="shoot_head_x", effect="headshot")]})
    _, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-06")
    assert "'shoot_head_x' uses effect 'headshot', which the engine does not have" in hit.message


def test_cnt06_unknown_label_placeholder(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "ph", {"affordances/test.yaml": [_affordance(core_pack_dir, id="odd_move", label="Walk to {place} now")]})
    _, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-06")
    assert hit.field == "label" and "{place}" in hit.message


def test_cnt10_anchor_names_are_noun_phrases():
    from as_engine.contracts.content import AnchorTemplate

    AnchorTemplate(name="gap behind the counter", kind="cover", x_m=1, y_m=1)
    with pytest.raises(Exception):
        AnchorTemplate(name="behind the counter", kind="cover", x_m=1, y_m=1)


def test_cnt07_lore_and_faction_need_truth_and_belief(tmp_path, core_pack_dir):
    faction = _raw(core_pack_dir, "factions/delgados_crew.yaml")
    faction = dict(faction, id="quiet_crew", belief_text="")
    root = make_pack(tmp_path, "lore7", {
        "lore/nobelief.md": lore_md("no_belief", "Nobody has ever seen the bottom of the quarry.", beliefs=[]),
        "factions/quiet.yaml": faction,
    })
    _, issues = issues_for(core_pack_dir, root)
    files = {i.file for i in issues if i.code == "CNT-07"}
    assert files == {"lore/nobelief.md", "factions/quiet.yaml"}


def test_cnt08_misspelling_is_error_retired_name_is_warning(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "names8", {
        "lore/a.md": lore_md("sotry_time", "The sotry of the quarry is older than the Fall."),
        "lore/b.md": lore_md("old_ledger", "The old PWOSS ledger was burned in the second winter."),
    })
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-08" and i.severity == "error" and i.file == "lore/a.md" for i in issues)
    assert any(i.code == "CNT-08" and i.severity == "warning" and i.file == "lore/b.md" for i in issues)
    assert not any(i.code == "CNT-08" and i.severity == "error" and i.file == "lore/b.md" for i in issues)


def test_cnt09_plausibility_expressions_parse(tmp_path, core_pack_dir):
    faction = _raw(core_pack_dir, "factions/delgados_crew.yaml")
    faction = dict(faction, id="bad_gate_crew")
    faction["presence"] = dict(faction["presence"], presence_conditions=["faction_density >> 2"])
    pc = _raw(core_pack_dir, "pcs/owen_marsh.yaml")
    pc = dict(pc, id="owen_copy")
    pc["plausibility_gate"] = dict(pc["plausibility_gate"], pass_any=["ammo >= 1 or melee"])
    pc["card"] = dict(pc["card"], one_line_identity="A second Owen, used only to test a broken gate")
    root = make_pack(tmp_path, "gate9", {"factions/bad.yaml": faction, "pcs/owen_copy.yaml": pc})
    _, issues = issues_for(core_pack_dir, root)
    assert {i.file for i in issues if i.code == "CNT-09"} == {"factions/bad.yaml", "pcs/owen_copy.yaml"}


def test_cnt10_specificity_minimums_name_the_field(tmp_path, core_pack_dir):
    person = _person()
    person["voice"]["would_never_say"] = ["Not my problem."]
    root = make_pack(tmp_path, "thin", {"actors/hal.yaml": person})
    canon, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-10")
    assert hit.file == "actors/hal.yaml" and hit.field == "voice.would_never_say"
    assert not canon.has("thin:actor/tester"), "a record that fails its contract is not loaded"


def test_cnt11_minor_safety_scans_values_and_ignores_negation(tmp_path, core_pack_dir):
    """CNT-11: a person under 18 plus any listed word is a hard error, negated or not; the same
    word on an adult record is not this rule's business; field NAMES are never scanned."""
    term = sorted(MINOR_UNSAFE_TERMS)[0]
    child = _person("kid_probe", name="Sam Probe", age=11, writers_notes=f"Scan probe word: {term}.")
    negated = _person("kid_probe_two", name="Lee Probe", age=12, writers_notes=f"Never {term}.")
    adult = _person("adult_probe", name="Dana Probe", age=35, writers_notes=f"Scan probe word: {term}.")
    root = make_pack(tmp_path, "safety", {"actors/kid.yaml": child, "actors/kid2.yaml": negated, "actors/adult.yaml": adult})
    _, issues = issues_for(core_pack_dir, root)
    hits = [i for i in issues if i.code == "CNT-11"]
    assert {i.file for i in hits} == {"actors/kid.yaml", "actors/kid2.yaml"}
    assert all(i.severity == "error" and i.field == "writers_notes" and term in i.message for i in hits)
    assert all("Scan probe word" not in i.message for i in hits), "never quote the surrounding text"


def test_cnt11_core_children_are_clean(canon):
    from as_engine.content.safety import unsafe_terms

    def values(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for v in o.values():  # values only: 'sex' is a field name, never scanned
                yield from values(v)
        elif isinstance(o, list):
            for v in o:
                yield from values(v)

    kids = [a for a in canon.all("actor") + canon.all("pc") if a.identity.age < 18]
    assert kids, "the core pack has at least one child (Eli)"
    for k in kids:
        for s in values(k.model_dump(mode="json")):
            assert unsafe_terms(s) == [], k.id


def test_cnt12_item_property_blocks(tmp_path, core_pack_dir):
    base = {"schema": "as.item.v1", "plural": "things", "mass_g": 900, "bulk": 2, "description": "Test item for CNT-12."}
    root = make_pack(tmp_path, "items12", {"items/x.yaml": [
        dict(base, id="naked_pistol", name="Pistol", kind="firearm"),
        dict(base, id="bat_tool", name="Bat", kind="tool", melee={"reach_m": 0.9, "damage_class": "medium", "wound_types": ["blunt"]}),
    ]})
    _, issues = issues_for(core_pack_dir, root)
    assert not [i for i in issues if i.code == "CNT-10"], "both records match the contract; only CNT-12 applies"
    assert {(i.field, i.message.split(": ", 1)[1].split("'")[1]) for i in issues if i.code == "CNT-12"} == {
        ("firearm", "naked_pistol"), ("melee", "bat_tool")}


def test_cnt13_quirk_written_for_another_creature(tmp_path, core_pack_dir):
    runner = _raw(core_pack_dir, "infected/runner.yaml")
    runner = runner[0] if isinstance(runner, list) else runner
    t = dict(runner, id="ZOMBIE_VARIANT_ID_TESTER01", name="Tester", quirks=["SHAM_MUTTER_LOOP"])
    root = make_pack(tmp_path, "inf13", {"infected/tester.yaml": t})
    _, issues = issues_for(core_pack_dir, root)
    hit = next(i for i in issues if i.code == "CNT-13")
    assert hit.field == "quirks[0]" and "SHAM_MUTTER_LOOP" in hit.message


def test_cnt13_crawler_may_use_shambler_quirks(canon):
    """Inheritance counts: the Crawler inherits the Shambler, so Shambler quirks fit it."""
    crawler = canon.find("infected", "ZOMBIE_ARCHETYPE_CRAWLER01")
    assert crawler.inherits == "ZOMBIE_ARCHETYPE_SHAMBLER01"


@pytest.mark.parametrize("variant", ["generation", "standing_brief"])
def test_cnt14_cheat_dossiers_only_in_cheat_packs(tmp_path, core_pack_dir, variant):
    person = _person("sneaky", name="Rex Sneak")
    if variant == "generation":
        person["generation"] = "cheat"
    else:
        person["tags"] = ["standing_brief"]
    root = make_pack(tmp_path, "notcheat", {"actors/sneaky.yaml": person})
    _, issues = issues_for(core_pack_dir, root)
    assert any(i.code == "CNT-14" for i in issues)
    ok = make_pack(tmp_path / "ok", "cheat_test", {"actors/sneaky.yaml": person})
    _, issues2 = issues_for(core_pack_dir, ok)
    assert not any(i.code == "CNT-14" for i in issues2)


# --------------------------------------------------------------------------- loader behaviour
def test_drafts_and_readmes_never_load_and_unknown_folders_warn(tmp_path, core_pack_dir):
    root = make_pack(tmp_path, "drafts", {
        "_drafts/actors/broken.yaml": "::: not yaml at all",
        "actors/README.md": "# notes\nTODO everything\n",
        "actors/_scratch.yaml": "::: nope",
        "maps/city.yaml": {"x": 1},
    })
    pack, issues = load_pack(root)
    assert pack is not None and not pack.records.get("actor")
    assert [i for i in issues if i.severity == "error"] == []
    assert any(i.code == "CNT-00" and i.severity == "warning" and i.file == "maps" for i in issues)


def test_dossier_as_markdown_keeps_body(tmp_path, core_pack_dir):
    person = _person("md_person", name="Ivo Mark")
    text = "---\n" + yaml.safe_dump(person, sort_keys=False) + "---\nIvo grew up above his father's bakery.\n"
    root = make_pack(tmp_path, "mdpack", {"actors/ivo.md": text})
    canon, issues = issues_for(core_pack_dir, root)
    assert not [i for i in issues if i.severity == "error"]
    assert canon.get("mdpack:actor/md_person").depth_reference.startswith("Ivo grew up")


def test_every_issue_names_its_file_first(tmp_path, core_pack_dir):
    person = _person()
    person["voice"]["would_never_say"] = []
    person["social"]["dependents"] = ["core:actor/nobody_at_all"]
    root = make_pack(tmp_path, "names", {"actors/hal.yaml": person})
    _, issues = issues_for(core_pack_dir, root)
    assert issues and all(i.message.startswith(i.file + ": ") for i in issues if i.file != "pack.yaml")


# --------------------------------------------------------------------------- compile
def _content_hash(canon):
    pairs = sorted((r, canonical_json(rec.model_dump(mode="json", by_alias=True)))
                   for k in canon.by_kind for r, rec in canon.by_kind[k].items())
    return hashlib.sha256(canonical_json([list(p) for p in pairs]).encode()).hexdigest()


def test_compile_writes_canon_and_is_deterministic(tmp_path, core_pack_dir, canon):
    out1, out2 = tmp_path / "a" / "canon.sqlite", tmp_path / "b" / "canon.sqlite"
    r1 = compile_packs([core_pack_dir], out1)
    r2 = compile_packs([core_pack_dir], out2)
    assert r1.ok and r2.ok and r1.content_hash == r2.content_hash == canon.content_hash == _content_hash(canon)
    assert r1.counts["actor"] == 10 and r1.counts["pc"] == 3
    con = sqlite3.connect(out1)
    row = con.execute("SELECT pack, json FROM actor WHERE ref = 'core:actor/mara_voss'").fetchone()
    assert row[0] == "core" and json.loads(row[1])["identity"]["name"].startswith("Mara")
    hits = [r[0] for r in con.execute("SELECT ref FROM lore_fts WHERE lore_fts MATCH 'tongue'")]
    assert "core:lore/tongue_strip_assay" in hits
    con.close()


def test_content_hash_changes_with_content(tmp_path, core_pack_dir, canon):
    copy_dir = tmp_path / "core"
    shutil.copytree(core_pack_dir, copy_dir)
    f = copy_dir / "items" / "weapons.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    data[0]["description"] = data[0]["description"] + " Someone scratched initials into it."
    f.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rep = compile_packs([copy_dir], tmp_path / "canon.sqlite")
    assert rep.ok and rep.content_hash != canon.content_hash


def test_compile_refuses_to_write_a_broken_canon(tmp_path, core_pack_dir):
    person = _person()
    person["voice"]["would_never_say"] = []
    root = make_pack(tmp_path, "broken", {"actors/hal.yaml": person})
    out = tmp_path / "canon.sqlite"
    rep = compile_packs([core_pack_dir, root], out)
    assert not rep.ok and any(i.code == "CNT-10" for i in rep.issues)
    assert not out.exists()
