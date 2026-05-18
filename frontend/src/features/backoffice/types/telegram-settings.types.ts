export type TelegramBotKind = "ops" | "support" | "system";

export type BackofficeTelegramSettings = {
  is_enabled: boolean;
  ops_enabled: boolean;
  support_enabled: boolean;
  system_enabled: boolean;
  ops_bot_token_masked: string;
  ops_chat_id: string;
  support_bot_token_masked: string;
  support_chat_id: string;
  system_bot_token_masked: string;
  system_chat_id: string;
  ops_notify_order_status: boolean;
  ops_notify_waybill_created: boolean;
  ops_notify_waybill_updated: boolean;
  ops_notify_waybill_deleted: boolean;
  support_notify_new_thread: boolean;
  support_notify_new_message: boolean;
  system_notify_backup_status: boolean;
  system_notify_import_status: boolean;
};

export type BackofficeTelegramSettingsPatch = Partial<{
  is_enabled: boolean;
  ops_enabled: boolean;
  support_enabled: boolean;
  system_enabled: boolean;
  ops_bot_token: string;
  ops_chat_id: string;
  support_bot_token: string;
  support_chat_id: string;
  system_bot_token: string;
  system_chat_id: string;
  ops_notify_order_status: boolean;
  ops_notify_waybill_created: boolean;
  ops_notify_waybill_updated: boolean;
  ops_notify_waybill_deleted: boolean;
  support_notify_new_thread: boolean;
  support_notify_new_message: boolean;
  system_notify_backup_status: boolean;
  system_notify_import_status: boolean;
}>;

export type BackofficeTelegramTestResponse = {
  ok: boolean;
  message: string;
};
