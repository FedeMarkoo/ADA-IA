"""Minimal validated planner: the model can propose actions, never execute them."""

from ada.domain.tasks import Action, Plan


class Planner:
    def __init__(self, registry, policy):
        self.registry = registry
        self.policy = policy

    def validate(self, plan):
        if not isinstance(plan, Plan):
            raise ValueError("El plan debe ser una instancia de Plan.")
        for action in plan.actions:
            if action.name not in self.registry:
                raise ValueError(f"Capability inexistente: {action.name}")
            # A dry-run plan is itself the preview; confirmation is required only at execution time.
            self.policy.authorize(action.name, action.arguments, confirmed=True)
        return plan

    def from_actions(self, actions, explanation=""):
        plan = Plan(
            actions=[item if isinstance(item, Action) else Action(**item) for item in actions],
            explanation=explanation,
            dry_run=True,
        )
        return self.validate(plan)
