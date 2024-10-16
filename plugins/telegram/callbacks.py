from airflow.providers.telegram.hooks.telegram import TelegramHook

from plugins.telegram.decorators import telegram_retry


@telegram_retry(max_retries=10)
def send_telegram(_context):
    hook = TelegramHook("airflow-telegram-monitoring")
    ti = _context["task_instance"]

    hook.send_message(
        api_params={
            "text": f"""
<b>⚠️ DAG <code>{ti.dag_id}</code> has Failed!</b>

    <b>Task: <code>{ti.task_id}</code> -FAILED</b>

<b>Exception:</b>
    <pre><code class="language-log">{_context['exception']}</code></pre>
""",
        }
    )
