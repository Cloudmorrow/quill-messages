"""Messages' tests: the real record store, its spaces and gate, on this machine.

Messages has no code: everything it does is declared in quill.toml and done
by the core's spaces and the thread kit. These hold what the manifest
promises — that a conversation is between its people and nobody else, that
one between two people is found from either side, and that a message and a
reaction are their author's.
"""

import pytest

from cloudmorrow.quill.testing import Harness

CONVERSATION = "messages.conversation"
MESSAGE = "messages.message"
REACTION = "messages.reaction"


@pytest.fixture()
def q():
    with Harness(".") as harness:
        yield harness


def between(q, *others, name=None, kind="direct", announce=False):
    """A conversation made the way the kit makes one: a shared space with its people in it."""
    record = q.state.records.create(
        q._principal(),
        CONVERSATION,
        {"name": name or ", ".join(others), "kind": kind},
        scope="shared",
        members=list(others),
        announce=announce,
    )
    return q.get(CONVERSATION, record.id)


def found_between(q, *others, kind="direct"):
    """What "write to somebody" finds before making anything: the one conversation with exactly these people."""
    found = q.state.records.find_space(q._principal(), CONVERSATION, {"kind": kind}, scope="shared", members=list(others))
    return found.id if found else None


def test_the_manifest_is_one_thread_of_conversations_between_people(q):
    (screen,) = q.manifest.screens
    assert screen["kit"] == "thread" and screen["model"] == MESSAGE and screen["space"] == "conversation"
    assert screen["made_as"] == {"direct": {"kind": "direct"}, "shared": {"kind": "group"}}
    assert screen["reactions"] == REACTION
    assert q.manifest.category == "personal"


def test_a_conversation_between_two_people_is_found_from_either_side(q):
    sara = q.as_user("sara")
    ours = between(q, "sara")
    assert found_between(q, "sara") == ours.id
    assert found_between(sara, q.user) == ours.id
    assert found_between(q, "ole") is None  # not the one with Ole


def test_what_is_written_is_read_by_the_people_in_it_and_nobody_else(q):
    sara, ole = q.as_user("sara"), q.as_user("ole")
    ours = between(q, "sara")
    q.seed(MESSAGE, conversation=ours.id, body="coffee at four?")
    sara.seed(MESSAGE, conversation=ours.id, body="yes")
    assert [m["body"] for m in sara.list(MESSAGE, conversation=ours.id)] == ["coffee at four?", "yes"]
    assert ole.list(CONVERSATION) == []
    assert ole.list(MESSAGE, conversation=ours.id) == []


def test_a_group_is_named_and_everybody_in_it_reads_it(q):
    sara, ole = q.as_user("sara"), q.as_user("ole")
    trip = between(q, "sara", "ole", name="Summer trip", kind="group")
    assert trip["name"] == "Summer trip" and trip["kind"] == "group"
    assert [c["name"] for c in ole.list(CONVERSATION)] == ["Summer trip"]
    sara.seed(MESSAGE, conversation=trip.id, body="who brings the tent?")
    assert [m["body"] for m in ole.list(MESSAGE, conversation=trip.id)] == ["who brings the tent?"]


def test_a_message_is_its_authors_to_change_or_take_back(q):
    sara = q.as_user("sara")
    ours = between(q, "sara")
    theirs = sara.seed(MESSAGE, conversation=ours.id, body="on my way")
    with pytest.raises(Exception):
        q.change(MESSAGE, theirs.id, body="on your way")
    with pytest.raises(Exception):
        q.delete(MESSAGE, theirs.id)
    assert sara.change(MESSAGE, theirs.id, body="here")["body"] == "here"
    sara.delete(MESSAGE, theirs.id)
    assert q.list(MESSAGE, conversation=ours.id) == []


def test_a_reaction_is_one_persons_and_theirs_to_take_back(q):
    sara = q.as_user("sara")
    ours = between(q, "sara")
    line = q.seed(MESSAGE, conversation=ours.id, body="we got the house")
    mine = sara.seed(REACTION, conversation=ours.id, message=line.id, emoji="❤️")
    assert [(r.owner, r["emoji"]) for r in q.list(REACTION, message=line.id)] == [("sara", "❤️")]
    with pytest.raises(Exception):
        q.delete(REACTION, mine.id)  # not mine to take back
    sara.delete(REACTION, mine.id)
    assert q.list(REACTION, message=line.id) == []


def test_what_somebody_else_writes_is_unread_until_you_look(q):
    sara = q.as_user("sara")
    ours = between(q, "sara")
    sara.seed(MESSAGE, conversation=ours.id, body="are you up?")
    # The unread count and the last line are what the record store puts on a space for its asker.
    spaces = q.state.records.list(q._principal(), CONVERSATION)
    (theirs,) = spaces
    assert theirs.unread == 1 and theirs.last["title"] == "are you up?"
    q.state.records.mark_seen(q._principal(), CONVERSATION, ours.id)
    (theirs,) = q.state.records.list(q._principal(), CONVERSATION)
    assert theirs.unread == 0


def test_a_conversation_goes_with_everything_in_it(q):
    sara = q.as_user("sara")
    ours = between(q, "sara")
    line = sara.seed(MESSAGE, conversation=ours.id, body="bye")
    sara.seed(REACTION, conversation=ours.id, message=line.id, emoji="👋")
    q.delete(CONVERSATION, ours.id)
    assert q.list(CONVERSATION) == []
    with pytest.raises(Exception):
        q.get(MESSAGE, line.id)


def test_a_conversation_held_elsewhere_says_so(q):
    # Room for a bridge: where a conversation is, whom it is with there, and
    # the service's own ids, on the conversation and on each message.
    theirs = q.state.records.create(
        q._principal(), CONVERSATION, {"name": "Mum", "kind": "direct", "via": "whatsapp", "address": "+45 12 34 56 78", "outside_id": "wa:1"}, scope="shared"
    )
    mum = q.get(CONVERSATION, theirs.id)
    assert mum["via"] == "whatsapp" and mum["address"] == "+45 12 34 56 78"
    assert [c.id for c in q.list(CONVERSATION, via="whatsapp", outside_id="wa:1")] == [mum.id]
    line = q.seed(MESSAGE, conversation=mum.id, body="landed safely", outside_id="wa:1:7")
    assert [m.id for m in q.list(MESSAGE, outside_id="wa:1:7")] == [line.id]
    # And one written here is here.
    ours = between(q, "sara")
    assert ours["via"] == "cloudmorrow"
