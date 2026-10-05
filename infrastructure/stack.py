"""Stage-one tables, identity, HTTP ingress and durable delivery with scoped IAM."""

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
from aws_cdk import aws_lambda as lambdas
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sqs as sqs
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct


class FoundationStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, callback_url: str):
        super().__init__(scope, construct_id, env=cdk.Environment(region="eu-west-1"))
        if stage not in {"dev", "prod"} or urlparse(callback_url).scheme != "https":
            raise ValueError("Stage and HTTPS callback must be configured")
        prefix = f"Koyori{stage.title()}"
        tables = {}
        for name in ("Domain", "Delivery", "Sessions"):
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
                )
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
                environment=environment,
                timeout=cdk.Duration.seconds(30),
                memory_size=256,
                reserved_concurrent_executions=4,
                log_group=group,
                tracing=lambdas.Tracing.ACTIVE,
            )
            functions[name] = fn
            # DynamoDB transaction permission is expressed by its underlying item operations.
            accessed = (
                ("Delivery",)
                if name == "publisher"
                else ("Domain", "Delivery")
                if name in {"workflow", "activity", "repair"}
                else ("Domain", "Delivery", "Sessions")
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
            if name == "api":
                cursor.grant_read(fn)
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
        api = apigw.HttpApi(
            self,
            "ControlApi",
            default_integration=HttpLambdaIntegration("ControlIntegration", functions["api"]),
            create_default_stage=True,
        )
        stage_resource = api.default_stage.node.default_child
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
