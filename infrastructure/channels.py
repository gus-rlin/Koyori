"""Isolated AgentCore runtimes and AppSync Events; image digests are deployment inputs."""

import aws_cdk as cdk
from aws_cdk import aws_appsync as appsync
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambdas
from aws_cdk import aws_logs as logs


def install(stack, *, stage, tables, functions, cursor, api, environment, code_path, callback_url):
    origin = callback_url.split("/", 3)[:3]
    origins = "/".join(origin)
    base = {
        **environment,
        "KOYORI_ALLOWED_ORIGINS": origins,
        "KOYORI_MCP_RESOURCE": api.api_endpoint + "/mcp",
        "KOYORI_SPEECH_REGION": "eu-north-1",
        "KOYORI_SPEECH_MODE": "aws",
    }
    for fn in functions.values():
        fn.add_environment("KOYORI_MCP_RESOURCE", api.api_endpoint + "/mcp")
        fn.add_environment("KOYORI_ALLOWED_ORIGINS", origins)
    functions["connector"].add_to_role_policy(
        iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:ConditionCheckItem"],
            resources=[tables["Sessions"].table_arn],
            conditions={
                "ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["CHANNELGRANT#*", "VOICE#*"]}
            },
        )
    )
    functions["api"].add_environment("KOYORI_SPEECH_MODE", "aws")
    functions["api"].add_environment("KOYORI_SPEECH_REGION", "eu-north-1")
    runtimes = {}
    for name, protocol, command, port in (
        ("Voice", "HTTP", "koyori.voice:create_voice_app", "8080"),
        ("Mcp", "MCP", "koyori.mcp_server:create_internal_app", "8000"),
    ):
        image = cdk.CfnParameter(
            stack,
            name + "ImageDigest",
            type="String",
            allowed_pattern=r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9/_-]+@sha256:[a-f0-9]{64}",
            description="Immutable ARM64 runtime image built from the reviewed lock and sources",
        )
        role = iam.Role(
            stack,
            name + "RuntimeRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": stack.account},
                    "ArnLike": {
                        "aws:SourceArn": stack.format_arn(
                            service="bedrock-agentcore", resource="runtime", resource_name="*"
                        )
                    },
                },
            ),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                resources=[
                    stack.format_arn(service="ecr", resource="repository", resource_name="koyori-*")
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"])
        )
        for table in ("Domain", "Delivery", "Sessions"):
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                        "dynamodb:PutItem",
                        "dynamodb:ConditionCheckItem",
                    ],
                    resources=[tables[table].table_arn, tables[table].table_arn + "/index/*"],
                )
            )
        cursor.grant_read(role)
        runtime_logs = stack.format_arn(
            service="logs",
            resource="log-group",
            resource_name=f"/aws/bedrock-agentcore/runtimes/koyori_{stage}_{name.lower()}-*",
            arn_format=cdk.ArnFormat.COLON_RESOURCE_NAME,
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:DescribeLogStreams",
                    "logs:PutResourcePolicy",
                ],
                resources=[runtime_logs],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[runtime_logs + ":log-stream:*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogGroups"],
                resources=[
                    stack.format_arn(
                        service="logs",
                        resource="log-group",
                        resource_name="*",
                        arn_format=cdk.ArnFormat.COLON_RESOURCE_NAME,
                    )
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            )
        )
        variables = {
            **base,
            "KOYORI_RUNTIME_MODULE": command,
            "KOYORI_RUNTIME_PORT": port,
            "KOYORI_CALENDAR_READER_ARN": functions["connector"].function_arn,
        }
        functions["connector"].grant_invoke(role)
        if name == "Voice":
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["bedrock:InvokeModelWithBidirectionalStream"],
                    resources=[
                        "arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-2-sonic-v1:0"
                    ],
                )
            )
            role.add_to_policy(
                iam.PolicyStatement(actions=["polly:SynthesizeSpeech"], resources=["*"])
            )
        else:
            variables["KOYORI_SPEECH_MODE"] = "disabled"
        runtime = agentcore.CfnRuntime(
            stack,
            name + "Runtime",
            agent_runtime_name=f"koyori_{stage}_{name.lower()}",
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image.value_as_string
                )
            ),
            role_arn=role.role_arn,
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            protocol_configuration=protocol,
            environment_variables=variables,
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(
                idle_runtime_session_timeout=60, max_lifetime=600
            ),
            request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", "Origin"]
            ),
        )
        runtimes[name] = runtime
        cdk.CfnOutput(stack, name + "RuntimeArn", value=runtime.attr_agent_runtime_arn)
    functions["api"].add_environment(
        "KOYORI_VOICE_RUNTIME_ARN", runtimes["Voice"].attr_agent_runtime_arn
    )
    functions["api"].add_environment(
        "KOYORI_MCP_RUNTIME_ARN", runtimes["Mcp"].attr_agent_runtime_arn
    )
    functions["api"].add_to_role_policy(
        iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[
                runtimes["Mcp"].attr_agent_runtime_arn,
                runtimes["Mcp"].attr_agent_runtime_arn + "/runtime-endpoint/*",
            ],
        )
    )
    functions["api"].add_to_role_policy(
        iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream"],
            resources=[
                runtimes["Voice"].attr_agent_runtime_arn,
                runtimes["Voice"].attr_agent_runtime_arn + "/runtime-endpoint/*",
            ],
        )
    )
    workers = {}
    for name, handler in (
        ("ChannelMaintenance", "koyori.realtime.tick"),
        ("SignalAuthorizer", "koyori.realtime.authorizer"),
    ):
        group = logs.LogGroup(
            stack,
            name + "Logs",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        fn = lambdas.Function(
            stack,
            name,
            runtime=lambdas.Runtime.PYTHON_3_12,
            handler=handler,
            code=lambdas.Code.from_asset(str(code_path)),
            environment=base,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            reserved_concurrent_executions=4,
            log_group=group,
            tracing=lambdas.Tracing.ACTIVE,
        )
        cursor.grant_read(fn)
        for table in ("Domain", "Delivery", "Sessions"):
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                        "dynamodb:PutItem",
                        "dynamodb:ConditionCheckItem",
                    ],
                    resources=[tables[table].table_arn, tables[table].table_arn + "/index/*"],
                )
            )
        workers[name] = fn
    authorizer = workers["SignalAuthorizer"]
    event_api = appsync.CfnApi(
        stack,
        "ActivityEvents",
        name=f"koyori-{stage}-activity",
        event_config=appsync.CfnApi.EventConfigProperty(
            auth_providers=[
                appsync.CfnApi.AuthProviderProperty(auth_type="AWS_IAM"),
                appsync.CfnApi.AuthProviderProperty(
                    auth_type="AWS_LAMBDA",
                    lambda_authorizer_config=appsync.CfnApi.LambdaAuthorizerConfigProperty(
                        authorizer_uri=authorizer.function_arn,
                        authorizer_result_ttl_in_seconds=0,
                        identity_validation_expression=r"^[A-Za-z0-9_-]{43}$",
                    ),
                ),
            ],
            connection_auth_modes=[appsync.CfnApi.AuthModeProperty(auth_type="AWS_LAMBDA")],
            default_publish_auth_modes=[appsync.CfnApi.AuthModeProperty(auth_type="AWS_IAM")],
            default_subscribe_auth_modes=[appsync.CfnApi.AuthModeProperty(auth_type="AWS_LAMBDA")],
        ),
    )
    authorizer.add_permission(
        "AppSyncAuthorize",
        principal=iam.ServicePrincipal("appsync.amazonaws.com"),
        source_arn=event_api.attr_api_arn,
    )
    appsync.CfnChannelNamespace(
        stack,
        "ActivityNamespace",
        api_id=event_api.attr_api_id,
        name="activity",
        publish_auth_modes=[appsync.CfnChannelNamespace.AuthModeProperty(auth_type="AWS_IAM")],
        subscribe_auth_modes=[appsync.CfnChannelNamespace.AuthModeProperty(auth_type="AWS_LAMBDA")],
    )
    realtime = "wss://" + event_api.attr_dns_realtime + "/event/realtime"
    for fn in (functions["api"], workers["ChannelMaintenance"]):
        fn.add_environment("KOYORI_REALTIME_URL", realtime)
        fn.add_environment("KOYORI_REALTIME_API_ID", event_api.attr_api_id)
    workers["ChannelMaintenance"].add_to_role_policy(
        iam.PolicyStatement(
            actions=["appsync:EventPublish"],
            resources=[event_api.attr_api_arn + "/channelNamespace/activity"],
        )
    )
    events.Rule(
        stack,
        "ChannelMaintenanceSchedule",
        schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
        targets=[targets.LambdaFunction(workers["ChannelMaintenance"], retry_attempts=2)],
    )
    cdk.CfnOutput(stack, "ActivityRealtimeUrl", value=realtime)
