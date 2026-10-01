"""Handler package. register_all() wires every handler; router MUST be last."""


def register_all(bot) -> None:
    from app.bot.handlers import (
        start, help, createenv, editenv, apps, deploy, bulk_deploy,
        app_controls, envs, env, importenv, deleteenv, delete_app,
        accounts, autodeploy, history, monitor, settings as settings_handler,
        createenv_flow,  # text-input dispatcher for conversation flows
        router,  # MUST be last (catch-all callbacks)
    )
    for module in (
        start, help, createenv, editenv, apps, deploy, bulk_deploy,
        app_controls, envs, env, importenv, deleteenv, delete_app,
        accounts, autodeploy, history, monitor, settings_handler,
        createenv_flow, router,
    ):
        module.register(bot)
