"""One consistent cohort snapshot; never infer historical completion from updated_at."""
import sqlalchemy as sa
from app.process_queries import ProcessQueries
from app.processing_state import messages, attachments
from app.storage_state import operations
from app.notification_model import NotificationError, checked_key

def report_range(period,anchor=None,from_date=None,to_date=None,*,now):
    """User-selected Berlin cohort boundaries; independent of mail scheduling."""
    from datetime import date,datetime,timedelta,timezone
    from app.notification_model import BERLIN,Slot,midnight
    try:
        today=datetime.fromtimestamp(now,timezone.utc).astimezone(BERLIN).date()
        day=date.fromisoformat(anchor) if anchor else today
        if period == "daily":start,end=day,day+timedelta(days=1)
        elif period == "weekly":
            start=day-timedelta(days=day.weekday());end=start+timedelta(days=7)
        elif period == "range":
            start=date.fromisoformat(from_date);end=date.fromisoformat(to_date)+timedelta(days=1)
            if not 0 < (end-start).days <= 366:raise ValueError()
        else:raise ValueError()
        first,last=midnight(start),midnight(end)
        return Slot("weekly" if period == "weekly" else "daily",first,last,first,last)
    except (TypeError,ValueError,OverflowError):
        raise NotificationError("notification_report_range_invalid",422) from None

def report_cohort(engine, slot, mailbox_key, *, as_of):
    if slot.kind not in {"daily", "weekly"} or type(as_of) is not int:
        raise NotificationError("notification_report_invalid", 422)
    checked_key(mailbox_key)
    with ProcessQueries(engine).snapshot() as c:
        cohort = sa.select(messages.c.message_key).where(messages.c.mailbox_key == mailbox_key,
            messages.c.created_at >= slot.start, messages.c.created_at < slot.end)
        count_mails = lambda *extra: c.execute(sa.select(sa.func.count()).select_from(messages).where(
            messages.c.message_key.in_(cohort), *extra)).scalar_one()
        count_attachments = lambda *extra: c.execute(sa.select(sa.func.count()).select_from(attachments).where(
            attachments.c.message_key.in_(cohort), *extra)).scalar_one()
        receipt = sa.exists(sa.select(operations.c.action_key).where(
            operations.c.action_key == attachments.c.effect_key,
            operations.c.state.in_(("stored", "duplicate"))))
        result = dict(messages=count_mails(), attachments=count_attachments(),
            unknown_open=count_attachments(ProcessQueries.unassigned()),
            stored_receipts=count_attachments(attachments.c.storage_state.in_(("stored", "duplicate")), receipt),
            duplicates=count_attachments(attachments.c.storage_state == "duplicate"),
            attachment_errors=count_attachments(sa.or_(attachments.c.effective_status == "failed",
                attachments.c.storage_state == "failed")),
            blocked_messages=count_mails(messages.c.state == "operator_required"))
        for category in ("E-Rechnung", "PDF", "Zahlungsavis", "Mahnung"):
            result[category] = count_attachments(attachments.c.category == category)
        return dict(start=slot.start, end=slot.end, as_of=as_of, counts=result)
