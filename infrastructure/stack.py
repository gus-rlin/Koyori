"""Durable control and stage-two connectors/projections, with separate credential roles."""

from pathlib import Path
from urllib.parse import urlparse

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_backup as backup
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambdas
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3vectors as vectors
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct


class FoundationStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        callback_url: str,
        google_client_id: str | None = None,
    ):
        super().__init__(scope, construct_id, env=cdk.Environment(region="eu-west-1"))
        if stage not in {"dev", "prod"} or urlparse(callback_url).scheme != "https":
            raise ValueError("Stage and HTTPS callback must be configured")
        prefix = f"Koyori{stage.title()}"
        tables = {}
        for name in ("Domain", "Delivery", "Sessions", "Connections"):
            table = ddb.Table(
                self,
                name,
                table_name=prefix + name,
                partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
                sort_key=ddb.Attribute(name="SK", type=ddb.AttributeType.STRING),
                billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                encryption=ddb.TableEncryption.AWS_MANAGED,
                point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True
                ),
                deletion_protection=True,
                removal_policy=cdk.RemovalPolicy.RETAIN,
                stream=ddb.StreamViewType.NEW_IMAGE if name == "Delivery" else None,
            )
            for index in ("GSI1", "GSI2"):
                table.add_global_secondary_index(
                    index_name=index,
                    partition_key=ddb.Attribute(name=f"{index}PK", type=ddb.AttributeType.STRING),
                    sort_key=ddb.Attribute(name=f"{index}SK", type=ddb.AttributeType.STRING),
                )
            tables[name] = table
        pool = cognito.UserPool(
            self,
            "Identity",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=False,
            account_recovery=cognito.AccountRecovery.NONE,
            mfa=cognito.Mfa.REQUIRED,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            password_policy=cognito.PasswordPolicy(min_length=14),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        resource = pool.add_resource_server(
            "ControlScopes",
            identifier="koyori",
            scopes=[
                cognito.ResourceServerScope(
                    scope_name="control", scope_description="Koyori control API"
                ),
                cognito.ResourceServerScope(
                    scope_name="mcp", scope_description="Resource-bound Koyori MCP"
                ),
            ],
        )
        client = pool.add_client(
            "ControlClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            access_token_validity=cdk.Duration.minutes(10),
            id_token_validity=cdk.Duration.minutes(5),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                callback_urls=[callback_url],
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.resource_server(
                        resource,
                        cognito.ResourceServerScope(
                            scope_name="control", scope_description="Koyori control API"
                        ),
                    ),
                    cognito.OAuthScope.resource_server(
                        resource,
                        cognito.ResourceServerScope(
                            scope_name="mcp", scope_description="Resource-bound Koyori MCP"
                        ),
                    ),
                ],
            ),
        )
        login = pool.add_domain(
            "ManagedLogin",
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"koyori-{stage}-{self.account}"
            ),
        )
        branding = cognito.CfnManagedLoginBranding(
            self,
            "ControlClientBranding",
            user_pool_id=pool.user_pool_id,
            client_id=client.user_pool_client_id,
            use_cognito_provided_values=True,
        )
        branding.node.add_dependency(login)
        cursor = secrets.Secret(
            self,
            "CursorSigningKey",
            generate_secret_string=secrets.SecretStringGenerator(
                password_length=48, exclude_punctuation=True
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        provider_key = kms.Key(
            self,
            "ProviderEnvelopeKey",
            enable_key_rotation=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        google_secret = secrets.Secret(
            self,
            "GoogleClientSecret",
            description="Replace with the Google OAuth client secret before qualification",
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        vector_name = f"koyori-{stage}-{self.account}-{self.region}-memory"
        vector_bucket = vectors.CfnVectorBucket(
            self,
            "MemoryVectors",
            vector_bucket_name=vector_name,
            encryption_configuration={"sseType": "AES256"},
        )
        vector_bucket.apply_removal_policy(cdk.RemovalPolicy.RETAIN)
        vector_index = vectors.CfnIndex(
            self,
            "MemoryIndex",
            vector_bucket_arn=vector_bucket.attr_vector_bucket_arn,
            index_name="memory-v1",
            data_type="float32",
            dimension=512,
            distance_metric="cosine",
        )
        vector_index.apply_removal_policy(cdk.RemovalPolicy.RETAIN)
        bus = events.EventBus(self, "DomainEvents")
        queues, dead_letters = {}, {}
        for name in ("workflow", "activity"):
            dlq = sqs.Queue(
                self,
                f"{name}DeadLetters",
                retention_period=cdk.Duration.days(14),
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                enforce_ssl=True,
            )
            queue = sqs.Queue(
                self,
                f"{name}Queue",
                visibility_timeout=cdk.Duration.minutes(6),
                retention_period=cdk.Duration.days(14),
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                enforce_ssl=True,
                dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=5),
            )
            queues[name], dead_letters[name] = queue, dlq
            rule = events.Rule(
                self,
                f"{name}Events",
                event_bus=bus,
                event_pattern=events.EventPattern(
                    source=["koyori.control"],
                    detail_type=[
                        "koyori.task.changed.v1",
                        "koyori.access.changed.v1",
                        "koyori.policy.changed.v1",
                        "koyori.memory.changed.v1",
                        "koyori.action.changed.v1",
                        "koyori.connection.changed.v1",
                        "koyori.calendar.changed.v1",
                    ],
                ),
            )
            rule.add_target(
                targets.SqsQueue(
                    queue,
                    dead_letter_queue=dlq,
                    retry_attempts=10,
                    max_event_age=cdk.Duration.hours(24),
                )
            )
        learning_enabled = self.node.try_get_context("learningEnabled")
        environment = {
            "KOYORI_ENV": stage,
            "KOYORI_TABLE_PREFIX": prefix,
            "KOYORI_ISSUER": pool.user_pool_provider_url,
            "KOYORI_CLIENT_ID": client.user_pool_client_id,
            "KOYORI_AUDIENCE": "koyori-control",
            "KOYORI_CURSOR_SECRET_ARN": cursor.secret_arn,
            "KOYORI_EVENT_BUS": bus.event_bus_name,
            "KOYORI_WORKFLOW_QUEUE_URL": queues["workflow"].queue_url,
            "KOYORI_ACTIVITY_QUEUE_URL": queues["activity"].queue_url,
            "KOYORI_LEARNING_MODE": "aws"
            if learning_enabled is True or learning_enabled == "true"
            else "disabled",
        }
        code_path = Path(__file__).resolve().parents[1] / "artifacts" / "lambda"
        if not (code_path / "koyori").is_dir():
            raise ValueError("Build the locked Lambda artifact before synthesis")
        functions = {}
        for name, handler in {
            "api": "koyori.control.lambda_handler.handler",
            "publisher": "koyori.workers.lambda_handlers.publish",
            "workflow": "koyori.workers.lambda_handlers.consume",
            "activity": "koyori.workers.lambda_handlers.project_activity",
            "repair": "koyori.workers.lambda_handlers.repair",
            "connector": "koyori.workers.stage2_runtime.connectors",
            "projection": "koyori.workers.stage2_runtime.projections",
            "coordinator": "koyori.workers.stage3_runtime.coordinate",
            "dispatch": "koyori.workers.stage3_runtime.dispatch",
            "scheduler": "koyori.workers.stage3_runtime.schedules",
            "notifications": "koyori.workers.stage3_runtime.notify",
            "learning": "koyori.workers.memory_runtime.learn",
        }.items():
            group = logs.LogGroup(
                self,
                f"{name}Logs",
                retention=logs.RetentionDays.TWO_WEEKS,
                removal_policy=cdk.RemovalPolicy.RETAIN,
            )
            fn = lambdas.Function(
                self,
                name,
                runtime=lambdas.Runtime.PYTHON_3_12,
                code=lambdas.Code.from_asset(str(code_path)),
                handler=handler,
                function_name=f"koyori-{stage}-scheduler" if name == "scheduler" else None,
                environment=environment,
                timeout=cdk.Duration.seconds(
                    180
                    if name == "connector"
                    else 100
                    if name == "coordinator"
                    else 60
                    if name in {"api", "projection", "learning"}
                    else 30
                ),
                memory_size=256,
                reserved_concurrent_executions=4,
                log_group=group,
                tracing=lambdas.Tracing.ACTIVE,
            )
            functions[name] = fn
            if name != "api":
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["dynamodb:GetItem", "dynamodb:ConditionCheckItem"],
                        resources=[tables["Sessions"].table_arn],
                        conditions={
                            "ForAllValues:StringEquals": {"dynamodb:LeadingKeys": ["RESTORE_FENCE"]}
                        },
                    )
                )
            # DynamoDB transaction permission is expressed by its underlying item operations.
            accessed = (
                ("Delivery",)
                if name == "publisher"
                else ("Domain", "Delivery")
                if name
                in {
                    "workflow",
                    "activity",
                    "repair",
                    "coordinator",
                    "dispatch",
                    "scheduler",
                    "notifications",
                    "learning",
                }
                else ("Domain", "Delivery", "Connections")
                if name == "connector"
                else ("Domain", "Delivery")
                if name == "projection"
                else ("Domain", "Delivery", "Sessions", "Connections")
            )
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                        "dynamodb:PutItem",
                        "dynamodb:ConditionCheckItem",
                    ],
                    resources=[
                        arn
                        for table_name in accessed
                        for arn in (
                            tables[table_name].table_arn,
                            tables[table_name].table_arn + "/index/*",
                        )
                    ],
                )
            )
            if name in {"publisher", "repair"}:
                bus.grant_put_events_to(fn)
            if name == "projection":
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem"],
                        resources=[tables["Domain"].table_arn],
                        conditions={
                            "ForAllValues:StringLike": {
                                "dynamodb:LeadingKeys": ["LEX#*", "LEXDOC#*"]
                            }
                        },
                    )
                )
            if name == "api":
                cursor.grant_read(fn)
            if name in {"api", "connector"}:
                fn.add_environment("KOYORI_TOKEN_KEY_ARN", provider_key.key_arn)
                fn.add_environment("KOYORI_GOOGLE_CLIENT_SECRET_ARN", google_secret.secret_arn)
                if google_client_id:
                    fn.add_environment("KOYORI_GOOGLE_CLIENT_ID", google_client_id)
                google_secret.grant_read(fn)
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["kms:GenerateDataKey", "kms:Decrypt"],
                        resources=[provider_key.key_arn],
                        conditions={"StringEquals": {"kms:EncryptionContext:env": stage}},
                    )
                )
            if name in {"api", "projection"}:
                fn.add_environment("KOYORI_SEMANTIC_MODE", "aws")
                fn.add_environment("KOYORI_VECTOR_BUCKET", vector_name)
                fn.add_environment("KOYORI_VECTOR_INDEX", "memory-v1")
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["bedrock:InvokeModel"],
                        resources=[
                            f"arn:{self.partition}:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                        ],
                    )
                )
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["s3vectors:PutVectors", "s3vectors:DeleteVectors"]
                        if name == "projection"
                        else ["s3vectors:QueryVectors", "s3vectors:GetVectors"],
                        resources=[vector_index.attr_index_arn],
                    )
                )
            cw.Alarm(
                self, f"{name}Errors", metric=fn.metric_errors(), threshold=1, evaluation_periods=1
            )
            cw.Alarm(
                self,
                f"{name}Throttles",
                metric=fn.metric_throttles(),
                threshold=1,
                evaluation_periods=1,
            )
        functions["publisher"].add_event_source(
            sources.DynamoEventSource(
                tables["Delivery"],
                starting_position=lambdas.StartingPosition.LATEST,
                batch_size=20,
                bisect_batch_on_error=True,
                report_batch_item_failures=True,
                retry_attempts=3,
                max_record_age=cdk.Duration.hours(24),
                on_failure=sources.SqsDlq(dead_letters["workflow"]),
                filters=[
                    lambdas.FilterCriteria.filter(
                        {
                            "eventName": ["INSERT", "MODIFY"],
                            "dynamodb": {
                                "NewImage": {
                                    "status": {"S": ["PENDING"]},
                                    "PK": {"S": [{"prefix": "OUTBOX#"}]},
                                }
                            },
                        }
                    )
                ],
            )
        )
        for name, queue in queues.items():
            functions[name].add_event_source(
                sources.SqsEventSource(
                    queue, batch_size=5, report_batch_item_failures=True, max_concurrency=2
                )
            )
            cw.Alarm(
                self,
                f"{name}Backlog",
                metric=queue.metric_approximate_age_of_oldest_message(),
                threshold=300,
                evaluation_periods=2,
            )
            cw.Alarm(
                self,
                f"{name}DeadLetterAlarm",
                metric=dead_letters[name].metric_approximate_number_of_messages_visible(),
                threshold=1,
                evaluation_periods=1,
            )
        events.Rule(
            self,
            "RepairSchedule",
            schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
            targets=[targets.LambdaFunction(functions["repair"], retry_attempts=2)],
        )
        coordinate_step = sfn_tasks.LambdaInvoke(
            self,
            "CoordinateFiniteRun",
            lambda_function=functions["coordinator"],
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        workflow_logs = logs.LogGroup(
            self,
            "CoordinationWorkflowLogs",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        machine = sfn.StateMachine(
            self,
            "CoordinationRuns",
            definition_body=sfn.DefinitionBody.from_chainable(coordinate_step),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=cdk.Duration.minutes(3),
            logs=sfn.LogOptions(
                destination=workflow_logs, include_execution_data=False, level=sfn.LogLevel.ERROR
            ),
            tracing_enabled=True,
        )
        functions["dispatch"].add_environment(
            "KOYORI_COORDINATOR_MACHINE_ARN", machine.state_machine_arn
        )
        machine.grant_start_execution(functions["dispatch"])
        functions["dispatch"].add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:DescribeExecution"],
                resources=[
                    self.format_arn(
                        service="states",
                        resource="execution",
                        resource_name=machine.state_machine_name + ":*",
                        arn_format=cdk.ArnFormat.COLON_RESOURCE_NAME,
                    )
                ],
            )
        )
        functions["coordinator"].add_environment("KOYORI_PLANNING_MODE", "aws")
        functions["coordinator"].add_environment("KOYORI_PLANNING_REGION", "us-east-1")
        functions["coordinator"].add_environment(
            "KOYORI_CALENDAR_READER_ARN", functions["connector"].function_arn
        )
        functions["connector"].grant_invoke(functions["coordinator"])
        functions["coordinator"].add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:{self.partition}:bedrock:us-east-1:{self.account}:inference-profile/us.amazon.nova-2-lite-v1:0",
                    *[
                        f"arn:{self.partition}:bedrock:{region}::foundation-model/amazon.nova-2-lite-v1:0"
                        for region in ("us-east-1", "us-east-2", "us-west-2")
                    ],
                ],
            )
        )
        functions["learning"].add_environment("KOYORI_PLANNING_REGION", "us-east-1")
        functions["learning"].add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:{self.partition}:bedrock:us-east-1:{self.account}:inference-profile/us.amazon.nova-2-lite-v1:0",
                    *[
                        f"arn:{self.partition}:bedrock:{region}::foundation-model/amazon.nova-2-lite-v1:0"
                        for region in ("us-east-1", "us-east-2", "us-west-2")
                    ],
                ],
            )
        )
        schedule_group = scheduler.CfnScheduleGroup(
            self, "WakeSchedules", name=f"koyori-{stage}-wakes"
        )
        schedule_role = iam.Role(
            self,
            "WakeSchedulerRole",
            assumed_by=iam.ServicePrincipal(
                "scheduler.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnEquals": {"aws:SourceArn": schedule_group.attr_arn},
                },
            ),
        )
        functions["scheduler"].grant_invoke(schedule_role)
        schedule_fn = functions["scheduler"]
        for key, value in {
            "KOYORI_SCHEDULER_GROUP": schedule_group.name,
            "KOYORI_SCHEDULER_ROLE_ARN": schedule_role.role_arn,
            "KOYORI_SCHEDULER_TARGET_ARN": self.format_arn(
                service="lambda",
                resource="function",
                resource_name=f"koyori-{stage}-scheduler",
                arn_format=cdk.ArnFormat.COLON_RESOURCE_NAME,
            ),
        }.items():
            schedule_fn.add_environment(key, value)
        schedule_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "scheduler:CreateSchedule",
                    "scheduler:GetSchedule",
                    "scheduler:DeleteSchedule",
                ],
                resources=[
                    self.format_arn(
                        service="scheduler",
                        resource="schedule",
                        resource_name=f"koyori-{stage}-wakes/*",
                    )
                ],
            )
        )
        schedule_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[schedule_role.role_arn],
                conditions={"StringEquals": {"iam:PassedToService": "scheduler.amazonaws.com"}},
            )
        )
        for role in (
            "connector",
            "projection",
            "dispatch",
            "scheduler",
            "notifications",
            "learning",
        ):
            events.Rule(
                self,
                f"{role}Schedule",
                schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
                targets=[targets.LambdaFunction(functions[role], retry_attempts=2)],
            )
        api = apigw.HttpApi(
            self,
            "ControlApi",
            default_integration=HttpLambdaIntegration("ControlIntegration", functions["api"]),
            create_default_stage=True,
        )
        stage_resource = api.default_stage.node.default_child
        from infrastructure.channels import install

        install(
            self,
            stage=stage,
            tables=tables,
            functions=functions,
            cursor=cursor,
            api=api,
            environment=environment,
            code_path=code_path,
            callback_url=callback_url,
        )
        for role in ("api", "connector"):
            functions[role].add_environment(
                "KOYORI_GOOGLE_REDIRECT_URI", api.api_endpoint + "/v1/oauth/google/callback"
            )
            functions[role].add_environment(
                "KOYORI_GOOGLE_WEBHOOK_URL", api.api_endpoint + "/v1/webhooks/google-calendar"
            )
        stage_resource.add_property_override("DefaultRouteSettings.ThrottlingBurstLimit", 20)
        stage_resource.add_property_override("DefaultRouteSettings.ThrottlingRateLimit", 10)
        vault = backup.BackupVault(self, "RecoveryVault", removal_policy=cdk.RemovalPolicy.RETAIN)
        plan = backup.BackupPlan(self, "DailyBackup", backup_vault=vault)
        plan.add_rule(
            backup.BackupPlanRule(
                schedule_expression=events.Schedule.cron(hour="2", minute="0"),
                delete_after=cdk.Duration.days(35),
            )
        )
        plan.add_selection(
            "Tables",
            resources=[
                backup.BackupResource.from_dynamo_db_table(table) for table in tables.values()
            ],
        )
        cdk.CfnOutput(self, "ApiUrl", value=api.api_endpoint)
        cdk.CfnOutput(self, "Issuer", value=pool.user_pool_provider_url)
        cdk.CfnOutput(self, "ClientId", value=client.user_pool_client_id)
        cdk.CfnOutput(self, "GoogleClientSecretArn", value=google_secret.secret_arn)
        cdk.CfnOutput(self, "ProviderEnvelopeKeyArn", value=provider_key.key_arn)
        cdk.CfnOutput(self, "MemoryVectorIndexArn", value=vector_index.attr_index_arn)
