from functools import cache
from typing import Optional

import schemas
from chalicelib.core import issues
from chalicelib.core.autocomplete import autocomplete
from chalicelib.core.sessions import sessions_metas
from chalicelib.utils import pg_client, helper
from chalicelib.utils.TimeUTC import TimeUTC
from chalicelib.utils.event_filter_definition import SupportedFilter, Event


def get_customs_by_session_id(session_id, project_id):
    with pg_client.PostgresClient() as cur:
        cur.execute(cur.mogrify("""\
            SELECT 
                c.*,
                'CUSTOM' AS type
            FROM events_common.customs AS c
            WHERE 
              c.session_id = %(session_id)s
            ORDER BY c.timestamp;""",
                                {"project_id": project_id, "session_id": session_id})
                    )
        rows = cur.fetchall()
    return helper.dict_to_camel_case(rows)


def __merge_cells(rows, start, count, replacement):
    rows[start] = replacement
    rows = rows[:start + 1] + rows[start + count:]
    return rows


def __get_grouped_clickrage(rows, session_id, project_id):
    click_rage_issues = issues.get_by_session_id(session_id=session_id, issue_type="click_rage", project_id=project_id)
    if len(click_rage_issues) == 0:
        return rows

    for c in click_rage_issues:
        merge_count = c.get("payload")
        if merge_count is not None:
            merge_count = merge_count.get("Count", 3)
        else:
            merge_count = 3
        for i in range(len(rows)):
            if rows[i]["timestamp"] == c["timestamp"]:
                rows = __merge_cells(rows=rows,
                                     start=i,
                                     count=merge_count,
                                     replacement={**rows[i], "type": "CLICKRAGE", "count": merge_count})
                break
    return rows


def get_by_session_id(session_id, project_id, group_clickrage=False, event_type: Optional[schemas.EventType] = None):
    with pg_client.PostgresClient() as cur:
        rows = []
        if event_type is None or event_type == schemas.EventType.CLICK:
            cur.execute(cur.mogrify("""\
                SELECT 
                    c.*,
                    'CLICK' AS type
                FROM events.clicks AS c
                WHERE 
                  c.session_id = %(session_id)s
                ORDER BY c.timestamp;""",
                                    {"project_id": project_id, "session_id": session_id})
                        )
            rows += cur.fetchall()
            if group_clickrage:
                rows = __get_grouped_clickrage(rows=rows, session_id=session_id, project_id=project_id)
        if event_type is None or event_type == schemas.EventType.INPUT:
            cur.execute(cur.mogrify("""
                SELECT 
                    i.*,
                    'INPUT' AS type
                FROM events.inputs AS i
                WHERE 
                  i.session_id = %(session_id)s
                ORDER BY i.timestamp;""",
                                    {"project_id": project_id, "session_id": session_id})
                        )
            rows += cur.fetchall()
        if event_type is None or event_type == schemas.EventType.LOCATION:
            cur.execute(cur.mogrify("""\
                SELECT 
                    l.*,
                    l.path AS value,
                    l.path AS url,
                    'LOCATION' AS type
                FROM events.pages AS l
                WHERE 
                  l.session_id = %(session_id)s
                ORDER BY l.timestamp;""", {"project_id": project_id, "session_id": session_id}))
            rows += cur.fetchall()
        rows = helper.list_to_camel_case(rows)
        rows = sorted(rows, key=lambda k: (k["timestamp"], k["messageId"]))
    return rows


def _search_tags(project_id, value, key=None, source=None):
    with pg_client.PostgresClient() as cur:
        query = f"""
        SELECT public.tags.name
               'TAG' AS type
        FROM public.tags
        WHERE public.tags.project_id = %(project_id)s
        ORDER BY SIMILARITY(public.tags.name, %(value)s) DESC
        LIMIT 10
        """
        query = cur.mogrify(query, {'project_id': project_id, 'value': value})
        cur.execute(query)
        results = helper.list_to_camel_case(cur.fetchall())
    return results


class EventType:
    CLICK = Event(ui_type=schemas.EventType.CLICK, table="events.clicks", column="label")
    INPUT = Event(ui_type=schemas.EventType.INPUT, table="events.inputs", column="label")
    LOCATION = Event(ui_type=schemas.EventType.LOCATION, table="events.pages", column="path")
    CUSTOM = Event(ui_type=schemas.EventType.CUSTOM, table="events_common.customs", column="name")
    REQUEST = Event(ui_type=schemas.EventType.REQUEST, table="events_common.requests", column="path")
    GRAPHQL = Event(ui_type=schemas.EventType.GRAPHQL, table="events.graphql", column="name")
    STATEACTION = Event(ui_type=schemas.EventType.STATE_ACTION, table="events.state_actions", column="name")
    TAG = Event(ui_type=schemas.EventType.TAG, table="events.tags", column="tag_id")
    ERROR = Event(ui_type=schemas.EventType.ERROR, table="events.errors",
                  column=None)  # column=None because errors are searched by name or message
    METADATA = Event(ui_type=schemas.FilterType.METADATA, table="public.sessions", column=None)
    #     MOBILE
    CLICK_MOBILE = Event(ui_type=schemas.EventType.CLICK_MOBILE, table="events_ios.taps", column="label")
    INPUT_MOBILE = Event(ui_type=schemas.EventType.INPUT_MOBILE, table="events_ios.inputs", column="label")
    VIEW_MOBILE = Event(ui_type=schemas.EventType.VIEW_MOBILE, table="events_ios.views", column="name")
    SWIPE_MOBILE = Event(ui_type=schemas.EventType.SWIPE_MOBILE, table="events_ios.swipes", column="label")
    CUSTOM_MOBILE = Event(ui_type=schemas.EventType.CUSTOM_MOBILE, table="events_common.customs", column="name")
    REQUEST_MOBILE = Event(ui_type=schemas.EventType.REQUEST_MOBILE, table="events_common.requests", column="path")
    CRASH_MOBILE = Event(ui_type=schemas.EventType.ERROR_MOBILE, table="events_common.crashes",
                         column=None)  # column=None because errors are searched by name or message


@cache
def supported_types():
    return {
        EventType.CLICK.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.CLICK),
                                                 query=autocomplete.__generic_query(typename=EventType.CLICK.ui_type)),
        EventType.INPUT.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.INPUT),
                                                 query=autocomplete.__generic_query(typename=EventType.INPUT.ui_type)),
        EventType.LOCATION.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.LOCATION),
                                                    query=autocomplete.__generic_query(
                                                        typename=EventType.LOCATION.ui_type)),
        EventType.CUSTOM.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.CUSTOM),
                                                  query=autocomplete.__generic_query(
                                                      typename=EventType.CUSTOM.ui_type)),
        EventType.REQUEST.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.REQUEST),
                                                   query=autocomplete.__generic_query(
                                                       typename=EventType.REQUEST.ui_type)),
        EventType.GRAPHQL.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.GRAPHQL),
                                                   query=autocomplete.__generic_query(
                                                       typename=EventType.GRAPHQL.ui_type)),
        EventType.STATEACTION.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.STATEACTION),
                                                       query=autocomplete.__generic_query(
                                                           typename=EventType.STATEACTION.ui_type)),
        EventType.TAG.ui_type: SupportedFilter(get=_search_tags, query=None),
        EventType.ERROR.ui_type: SupportedFilter(get=autocomplete.__search_errors,
                                                 query=None),
        EventType.METADATA.ui_type: SupportedFilter(get=autocomplete.__search_metadata,
                                                    query=None),
        #     MOBILE
        EventType.CLICK_MOBILE.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.CLICK_MOBILE),
                                                        query=autocomplete.__generic_query(
                                                            typename=EventType.CLICK_MOBILE.ui_type)),
        EventType.SWIPE_MOBILE.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.SWIPE_MOBILE),
                                                        query=autocomplete.__generic_query(
                                                            typename=EventType.SWIPE_MOBILE.ui_type)),
        EventType.INPUT_MOBILE.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.INPUT_MOBILE),
                                                        query=autocomplete.__generic_query(
                                                            typename=EventType.INPUT_MOBILE.ui_type)),
        EventType.VIEW_MOBILE.ui_type: SupportedFilter(get=autocomplete.__generic_autocomplete(EventType.VIEW_MOBILE),
                                                       query=autocomplete.__generic_query(
                                                           typename=EventType.VIEW_MOBILE.ui_type)),
        EventType.CUSTOM_MOBILE.ui_type: SupportedFilter(
            get=autocomplete.__generic_autocomplete(EventType.CUSTOM_MOBILE),
            query=autocomplete.__generic_query(
                typename=EventType.CUSTOM_MOBILE.ui_type)),
        EventType.REQUEST_MOBILE.ui_type: SupportedFilter(
            get=autocomplete.__generic_autocomplete(EventType.REQUEST_MOBILE),
            query=autocomplete.__generic_query(
                typename=EventType.REQUEST_MOBILE.ui_type)),
        EventType.CRASH_MOBILE.ui_type: SupportedFilter(get=autocomplete.__search_errors_mobile,
                                                        query=None),
    }


def get_errors_by_session_id(session_id, project_id):
    with pg_client.PostgresClient() as cur:
        cur.execute(cur.mogrify(f"""\
                    SELECT er.*,ur.*, er.timestamp - s.start_ts AS time
                    FROM {EventType.ERROR.table} AS er INNER JOIN public.errors AS ur USING (error_id) INNER JOIN public.sessions AS s USING (session_id)
                    WHERE er.session_id = %(session_id)s AND s.project_id=%(project_id)s
                    ORDER BY timestamp;""", {"session_id": session_id, "project_id": project_id}))
        errors = cur.fetchall()
        for e in errors:
            e["stacktrace_parsed_at"] = TimeUTC.datetime_to_timestamp(e["stacktrace_parsed_at"])
        return helper.list_to_camel_case(errors)


def search(text, event_type, project_id, source, key):
    if not event_type:
        return {"data": autocomplete.__get_autocomplete_table(text, project_id)}

    if event_type in supported_types().keys():
        rows = supported_types()[event_type].get(project_id=project_id, value=text, key=key, source=source)
    elif event_type + "_MOBILE" in supported_types().keys():
        rows = supported_types()[event_type + "_MOBILE"].get(project_id=project_id, value=text, key=key, source=source)
    elif event_type in sessions_metas.supported_types().keys():
        return sessions_metas.search(text, event_type, project_id)
    elif event_type.endswith("_IOS") \
            and event_type[:-len("_IOS")] in sessions_metas.supported_types().keys():
        return sessions_metas.search(text, event_type, project_id)
    elif event_type.endswith("_MOBILE") \
            and event_type[:-len("_MOBILE")] in sessions_metas.supported_types().keys():
        return sessions_metas.search(text, event_type, project_id)
    else:
        return {"errors": ["unsupported event"]}

    return {"data": rows}
