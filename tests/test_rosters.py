import pandas as pd
import pytest

from fantasyhelper.rosters import build_roster_update, fetch_local_rosters


def test_build_roster_update_assigns_owners_and_undrafted_players():
    rosters = pd.DataFrame(
        {"FullName": ["Nathan MacKinnon", "John-Jason Peterka"],
         "manager": ["Phil", "Rob"], "fantasy_team": ["Team Phil", "Team Rob"]}
    )

    update = build_roster_update(
        ["Nathan MacKinnon", "John Jason Peterka", "Nobody"], rosters, {"Rob": "Rob/Orad"}
    )

    assert update.values == [["Phil"], ["Rob/Orad"], ["Undrafted"]]
    assert update.matched_players == 2
    assert update.yahoo_players_not_on_sheet == []


def test_build_roster_update_does_not_guess_when_two_owners_claim_a_player():
    rosters = pd.DataFrame(
        {"FullName": ["Alex Smith", "Alex Smith"], "manager": ["Phil", "Lev"],
         "fantasy_team": ["A", "B"]}
    )

    update = build_roster_update(["Alex Smith"], rosters)

    assert update.values == [["Undrafted"]]
    assert update.ambiguous_sheet_players == ["Alex Smith"]


def test_build_roster_update_rejects_an_unrecognized_yahoo_team_name():
    rosters = pd.DataFrame(
        {"FullName": ["Alex Smith"], "manager": ["A New Name"], "fantasy_team": ["A New Name"]}
    )

    with pytest.raises(ValueError, match="Unrecognized Yahoo team name 'A New Name'"):
        build_roster_update(["Alex Smith"], rosters, {"Phil": "Phil"}, ["Phil"])


def test_fetch_local_rosters_parses_yahoo_team_tables(tmp_path):
    page = tmp_path / "rosters.html"
    page.write_text('''<div><p><a href="/hockey/5325/1">Slafter Revenge</a></p>
    <table id="Tst-team-1"><a class="Nowrap name F-link playernote" title="Robert Thomas">Robert Thomas</a>
    <a class="Nowrap name F-link playernote" title="Wyatt Johnston">Wyatt Johnston</a></table>''')

    rosters = fetch_local_rosters(str(page))

    assert rosters.to_dict("records") == [
        {"FullName": "Robert Thomas", "manager": "Slafter Revenge", "fantasy_team": "Slafter Revenge", "is_ir": False, "team": "", "position": ""},
        {"FullName": "Wyatt Johnston", "manager": "Slafter Revenge", "fantasy_team": "Slafter Revenge", "is_ir": False, "team": "", "position": ""},
    ]


def test_fetch_local_rosters_marks_ir_slot_and_status_as_ir(tmp_path):
    page = tmp_path / "rosters.html"
    page.write_text('''<div><p><a href="/hockey/5325/1">Slafter Revenge</a></p>
    <table id="Tst-team-1">
    <tr><td class="pos first">IR+</td><td><a class="Nowrap name F-link playernote" title="Brock Faber">Brock Faber</a></td></tr>
    <tr><td class="pos first">BN</td><td><a class="Nowrap name F-link playernote" title="Connor Bedard">Connor Bedard</a><span title="Injured Reserve – Non-Roster">IR-NR</span></td></tr>
    </table>''')

    rosters = fetch_local_rosters(str(page))

    assert rosters["is_ir"].tolist() == [True, True]
    update = build_roster_update(["Brock Faber", "Connor Bedard"], rosters)
    assert update.values == [["IR"], ["IR"]]


def test_fetch_local_rosters_extracts_current_nhl_team_and_position(tmp_path):
    page = tmp_path / "rosters.html"
    page.write_text('''<div><p><a href="/hockey/5325/1">Slafter Revenge</a></p>
    <table id="Tst-team-1"><tr><td class="pos first">BN</td><td>
    <a class="Nowrap name F-link playernote" title="Dylan Garand">Dylan Garand</a>
    <span class="D-b"><span class="Fz-xxs">NYR - G</span></span>
    </td></tr></table>''')

    roster = fetch_local_rosters(str(page)).iloc[0]

    assert roster["team"] == "NYR"
    assert roster["position"] == "G"
