from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoControlSubscriberPolicyMap,
    CiscoServicePolicyControlSubscriber,
    CiscoAccessSessionMonitor,
    PolicyMapAction,
    PolicyMapClass,
    PolicyMapEvent,
)

AUTHENTICATE_DOT1X = "authenticate using dot1x retries 2 retry-time 0 priority 10"
AUTHENTICATE_MAB   = "authenticate using mab priority 20"


class SetDot1xPolicy(ConfigMap):
    def compile(self, context):

        event_session_started = PolicyMapEvent(
            event_type="session-started",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="always", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action=AUTHENTICATE_DOT1X),
                    ],
                ),
            ],
        )

        event_auth_failure = PolicyMapEvent(
            event_type="authentication-failure",
            match_type="match-first",
            classes=[
                PolicyMapClass(
                    priority=5, class_name="DOT1X_FAILED", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate dot1x"),
                        PolicyMapAction(priority=20, action=AUTHENTICATE_MAB),
                    ],
                ),
                PolicyMapClass(
                    priority=10, class_name="AAA_SVR_DOWN_UNAUTHD_HOST", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="activate service-template DefaultCriticalAuthVlan_SRV_TEMPLATE"),
                        PolicyMapAction(priority=20, action="activate service-template DefaultCriticalVoice_SRV_TEMPLATE"),
                        PolicyMapAction(priority=30, action="authorize"),
                        PolicyMapAction(priority=40, action="pause reauthentication"),
                    ],
                ),
                PolicyMapClass(
                    priority=20, class_name="AAA_SVR_DOWN_AUTHD_HOST", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="pause reauthentication"),
                        PolicyMapAction(priority=20, action="authorize"),
                    ],
                ),
                PolicyMapClass(
                    priority=30, class_name="DOT1X_NO_RESP", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate dot1x"),
                        PolicyMapAction(priority=20, action=AUTHENTICATE_MAB),
                    ],
                ),
                PolicyMapClass(
                    priority=40, class_name="MAB_FAILED", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate mab"),
                        PolicyMapAction(priority=20, action="authentication-restart 60"),
                    ],
                ),
                PolicyMapClass(
                    priority=50, class_name="DOT1X_TIMEOUT", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate dot1x"),
                        PolicyMapAction(priority=20, action=AUTHENTICATE_MAB),
                    ],
                ),
                PolicyMapClass(
                    priority=60, class_name="always", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate dot1x"),
                        PolicyMapAction(priority=20, action="terminate mab"),
                        PolicyMapAction(priority=30, action="authentication-restart 60"),
                    ],
                ),
            ],
        )

        event_aaa_available = PolicyMapEvent(
            event_type="aaa-available",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="IN_CRITICAL_AUTH_CLOSED_MODE", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="clear-session"),
                    ],
                ),
                PolicyMapClass(
                    priority=20, class_name="NOT_IN_CRITICAL_AUTH_CLOSED_MODE", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="resume reauthentication"),
                    ],
                ),
            ],
        )

        event_agent_found = PolicyMapEvent(
            event_type="agent-found",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="always", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="terminate mab"),
                        PolicyMapAction(priority=20, action=AUTHENTICATE_DOT1X),
                    ],
                ),
            ],
        )

        event_inactivity_timeout = PolicyMapEvent(
            event_type="inactivity-timeout",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="always", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="clear-session"),
                    ],
                ),
            ],
        )

        event_auth_success = PolicyMapEvent(
            event_type="authentication-success",
            match_type="match-all",
            classes=[],
        )

        event_violation = PolicyMapEvent(
            event_type="violation",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="always", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="restrict"),
                    ],
                ),
            ],
        )

        event_authz_failure = PolicyMapEvent(
            event_type="authorization-failure",
            match_type="match-all",
            classes=[
                PolicyMapClass(
                    priority=10, class_name="AUTHC_SUCCESS-AUTHZ_FAIL", mode="do-until-failure",
                    actions=[
                        PolicyMapAction(priority=10, action="authentication-restart 60"),
                    ],
                ),
            ],
        )

        dot1x_policy = CiscoControlSubscriberPolicyMap(
            name="DOT1X_POLICY",
            events=[
                event_session_started,
                event_auth_failure,
                event_aaa_available,
                event_agent_found,
                event_inactivity_timeout,
                event_auth_success,
                event_violation,
                event_authz_failure,
            ],
        )
        context.configuration.add(dot1x_policy)

        context.configuration.add(
            CiscoServicePolicyControlSubscriber(policy_name=dot1x_policy)
        )

        context.configuration.add(CiscoAccessSessionMonitor(enabled=True))


config = SetDot1xPolicy()
config.filters = FilterAttribute("role").eq("/.*/")