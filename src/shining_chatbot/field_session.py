"""Session boundary between one field site and another."""

from __future__ import annotations

from collections.abc import MutableMapping


ONE_OFF_WIDGET_KEYS = (
    "one_off_site", "one_off_activity", "one_off_day", "one_off_start", "one_off_area",
    "one_off_end", "one_off_location", "one_off_equipment", "one_off_contractor",
    "one_off_owner", "one_off_people", "one_off_controls", "one_off_follow_up",
)

SITE_SCOPED_KEYS = (
    "field_reviews", "field_actions", "field_tbm_records", "field_tbm_deliveries",
    "field_weather_location", "field_weather_plan_status", "field_location_candidates", "field_revisions",
    "field_incident_frame", "field_incident_name", "field_incident_scope", "field_incident_token",
    "field_incident_scope_input", "field_incident_upload_version", "field_item_choice", "field_selected_action",
    "field_action_filter", "field_action_query", "field_action_notice",
    "field_pattern_day", "field_pattern_range", "field_pattern_type_filter",
    "chat_work_file", "chat_attached_item",
    "field_weather_error",
    "tbm_delivery_actor", "tbm_attendee_count", "tbm_delivery_note", "tbm_delivery_ack",
    "tbm_day", "tbm_available_days", "field_weather_candidate", "field_weather_query",
    "rag_context", "rag_equipment", "rag_industry", "rag_messages", "_chat_data_token",
    *ONE_OFF_WIDGET_KEYS, "field_backup_upload", "field_restored_token",
)


def clear_site_context(state: MutableMapping, *, preserve: tuple[str, ...] = ()) -> None:
    for key in SITE_SCOPED_KEYS:
        if key not in preserve:
            state.pop(key, None)
    widget_prefixes = (
        "review_status_", "reviewer_", "review_note_", "action_description_",
        "action_assignee_", "action_due_day_", "action_due_time_",
        "complete_actor_", "complete_note_", "reopen_actor_", "reopen_reason_",
        "field_incident_upload_", "field_no_work_by_", "field_no_work_note_", "field_no_work_ack_",
    )
    for key in tuple(state):
        if key not in preserve and key.startswith(widget_prefixes):
            state.pop(key, None)
