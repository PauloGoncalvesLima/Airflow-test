with state_map as (
select
	'accepted' as "state",
	'Aceita ' as "label",
	'✅ ✅ ✅' as "emoji"
union all
select
	'evaluating' as "state",
	'Em avaliação ' as "label",
	'📥 📥 📥' as "emoji"
union all
select
	'withdrawn' as "state",
	'Retirada ' as "label",
	'🚫 🚫 🚫' as "emoji"
union all
select
	'rejected' as "state",
	'Rejeitada ' as "label",
	'⛔ ⛔ ⛔' as "emoji"
union all
select
	'others' as "state",
	'Atualizada ' as "label",
	'🔄 🔄 🔄' as "emoji"
union all
select
	'new' as "state",
	'' as "label",
	'📣 📣 📣 <b>[NOVA]</b>' as "emoji"),
full_proposals as (
select
	processes.id as processes_ids,
	processes.slug as processes_slugs,
	processes.group_chat_id as telegram_group_chat_id,
	proposals.id as proposals_ids,
	proposals.decidim_component_id as components_ids,
	DATE_TRUNC('second',
	proposals.created_at) at TIME zone 'UTC' as created_at,
	DATE_TRUNC('second',
	proposals.updated_at) at TIME zone 'UTC' as updated_at,
	cast(proposals.title->'pt-BR' as text) as proposal_title,
	cast(proposals.body->'pt-BR' as text) as body,
	coalesce(state_map.label,
	'Atualizada ') as label,
	coalesce(state_map.emoji,
	'🔄 🔄 🔄') as emoji,
	scopes."name"->'pt-BR' as category,
	'https://brasilparticipativo.presidencia.gov.br/processes/' || processes.slug || '/f/' || components.id || '/proposals/' || proposals.id as proposal_link
from
	decidim_proposals_proposals proposals
inner join decidim_components components on
	components.id = proposals.decidim_component_id
inner join decidim_participatory_processes processes on
	processes.id = components.participatory_space_id
left join decidim_scopes scopes on
	proposals.decidim_scope_id = scopes.id
left join state_map on
	state_map.state = 
    case
		when DATE_TRUNC('second', proposals.created_at) at TIME zone 'UTC' <	DATE_TRUNC('second', proposals.updated_at) at TIME zone 'UTC' then proposals.state
		else 'new'
	end
where
	processes.group_chat_id notnull
	and processes.group_chat_id <> ''
	and components.manifest_name = 'proposals'
	and components.settings->'global'->'participatory_texts_enabled' = 'false'
	and processes.end_date >= current_date
	and components.published_at notnull)
select
	full_proposals.processes_ids,
	full_proposals.processes_slugs,
	full_proposals.telegram_group_chat_id,
	full_proposals.proposals_ids,
--	full_proposals.proposal_link,
--	full_proposals.created_at,
	full_proposals.updated_at,
	coalesce(body,	'') as body,
	full_proposals.emoji || ' ' || full_proposals.label || 'proposta <b></b>em ' || coalesce(to_char(full_proposals.updated_at, 'HH24:MI'),	'') || '

' 	|| '<a href="' || full_proposals.proposal_link || '">Acesse aqui</a>' || '

'
 	|| '<b>Proposta</b>
' 	|| REPLACE(coalesce(full_proposals.proposal_title::text,	'-'), '"', '') || '

'
 	|| '<b>Categoria</b>
' 	|| REPLACE(coalesce(full_proposals.category::text,	'-'), '"', '') || '

'
 	|| '<b>Descrição</b>
' as telegram_message
from
	full_proposals
where
	full_proposals.updated_at >= '{last_update_time}'
	and full_proposals.processes_ids = '{processes_id}'