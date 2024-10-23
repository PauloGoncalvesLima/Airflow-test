CREATE TABLE "telegram-moderation".telegram_channels (
	participatory_space_id text NULL,
	slug text NULL,
	telegram_group_chat_id text NULL,
	telegram_topic_type text NULL,
	telegram_topic_id text NULL,
	last_message_sent varchar DEFAULT '2023-01-01 12:00:00.000 -0300'::character varying NULL
);