select
	participatory_processes.id as participatory_space_id,
	participatory_processes.slug,
	participatory_processes.group_chat_id as telegram_group_chat_id
from
	decidim_participatory_processes participatory_processes
inner join decidim_components components on
	participatory_processes.id = components.participatory_space_id
where
	participatory_processes.group_chat_id notnull
	and participatory_processes.group_chat_id <> ''
	and components.manifest_name = 'proposals'
	and participatory_processes.end_date >= current_date
	and components.published_at notnull
group by 1, 2;