from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import send_email, send_fcm, send_socketio


@workflow.defn
class NotificationWorkflow:
    @workflow.run
    async def run(self, user_id: str) -> dict:
        retry_policy = RetryPolicy(maximum_attempts=5)
        timeout = timedelta(seconds=30)

        email_result = await workflow.execute_activity(
            send_email,
            user_id,
            start_to_close_timeout=timeout,
            retry_policy=retry_policy,
        )

        fcm_result = await workflow.execute_activity(
            send_fcm,
            user_id,
            start_to_close_timeout=timeout,
            retry_policy=retry_policy,
        )

        sio_result = await workflow.execute_activity(
            send_socketio,
            user_id,
            start_to_close_timeout=timeout,
            retry_policy=retry_policy,
        )

        return {
            "email": email_result,
            "fcm": fcm_result,
            "socketio": sio_result,
        }
