# Zapier Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `zapier-webhook` (bridge к Zapier Zaps).

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(account) + `ui.Divider` + navigation `ui.ListItem`(Outgoing Webhook/Inbound Events) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Outgoing Webhook Config (center, `center_overlay=True`) | `ui.KeyValue`(webhook URL configured — да/нет) + `ui.Input`(param_name="webhook_url", placeholder="Catch Hook URL из Zapier...") + `ui.Button`("Сохранить") | Единственный сконфигурированный outgoing webhook (не список — у Zapier Connector один "Catch Hook" URL), прямая форма без лишней навигации. |
| Send Test Event Dialog | `ui.Dialog`(title="Отправить тестовое событие?", content=`ui.TextArea`(param_name="payload_json", placeholder="JSON payload события..."), confirm_label="Отправить") | Отправка события в реальный Zap — обязателен `Dialog` с подтверждением содержимого. |
| Inbound Events List | `ui.DataTable`(received_at, preview; sortable) | Табличный обзор входящих событий, которые Zap уже отправил через наш webhook. |
| Inbound Event Detail | Back-button + `ui.Code`(language="json", full body+headers, readonly) | `Code`(json) для полного просмотра сырого payload события. |
| App Settings | `ui.Accordion`([Inbound Webhook URL + Regenerate Secret]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__zapier_sidebar` рендерит account + разделы,
   `auto_action` открывает Outgoing Webhook Config (показывает, настроен ли URL).
2. Ввод/изменение URL → `ui.Call("set_outgoing_webhook")` → `refresh_panels`.
3. "Отправить тестовое событие" → `ui.Dialog` с JSON payload → `ui.Call("send_webhook_event")`.
4. Inbound Events List — read-only лог; клик на событие → Inbound Event Detail.
5. App Settings — только через кнопку в сайдбаре; Regenerate Secret оформляется
   отдельной кнопкой с `ui.Dialog` подтверждением (старый секрет сразу перестаёт
   работать — деструктивно-лёгкое действие).

## 3. Экраны/карточки (артефакты для реализации)

- `panels.py`: `__panel__zapier_sidebar` (left).
- `panels_webhook.py`: `__panel__outgoing_webhook_config` (center, `center_overlay=True`).
- `panels_inbound.py`: `__panel__inbound_events_list` (center),
  `__panel__inbound_event_detail` (center, параметризован `event_id`, Code json).
- `panels_settings.py`: `__panel__app_settings` (center overlay, Accordion,
  webhook URL + regenerate secret).
