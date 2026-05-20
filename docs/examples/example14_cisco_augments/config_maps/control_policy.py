from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoControlSubscriberPolicyMap,
    CiscoServicePolicyControlSubscriber,
    CiscoAccessSessionMonitor,
    PolicyMapAction,
    PolicyMapClass,
    PolicyMapEvent,
)


class SetControlPolicy(ConfigMap):
    def compile(self, context):
        action_authorize = PolicyMapAction(priority=10, action="authorize")

        cls_always = PolicyMapClass(
            priority=10,
            class_name="always",
            mode="do-until-failure",
            actions=[action_authorize],
        )

        event_session_started = PolicyMapEvent(
            event_type="session-started",
            match_type="match-all",
            classes=[cls_always],
        )

        ise_policy = CiscoControlSubscriberPolicyMap(
            name="ISE_VISIBILITY",
            events=[event_session_started],
        )
        context.configuration.add(ise_policy)

        context.configuration.add(
            CiscoServicePolicyControlSubscriber(policy_name=ise_policy)
        )

        context.configuration.add(CiscoAccessSessionMonitor(enabled=True))


config = SetControlPolicy()
config.filters = FilterAttribute("role").eq("ise_visibility")
