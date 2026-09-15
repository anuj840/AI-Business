from app.models.business import DEAL_STATUS_TERMINAL, DealStatus


def test_terminal_statuses_are_exactly_the_dead_end_ones():
    assert DEAL_STATUS_TERMINAL == {
        DealStatus.NOT_INTERESTED,
        DealStatus.DO_NOT_CONTACT,
        DealStatus.CONVERTED,
    }


def test_active_statuses_are_not_terminal():
    for status in (DealStatus.NEW, DealStatus.CONTACTED, DealStatus.REPLIED, DealStatus.INTERESTED):
        assert status not in DEAL_STATUS_TERMINAL
