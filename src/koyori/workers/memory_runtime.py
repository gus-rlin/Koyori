"""A dedicated model role; projection and provider recovery have independent budgets."""


def learn(event, context):
    from koyori.auto_learning import AutoLearning
    from koyori.workers.runtime import engine

    return {"attempted": AutoLearning(engine().domain).sweep()}
