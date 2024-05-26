import * as cdk from 'aws-cdk-lib';
import * as path from 'path';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as ddb from 'aws-cdk-lib/aws-dynamodb';


export class AgentInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const vpc = ec2.Vpc.fromLookup(this, 'VPC', {
      isDefault: true,
    });

    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
    });

    const taskDefinition = new ecs.FargateTaskDefinition(this, 'TaskDefinition', {
      memoryLimitMiB: 2048,
      cpu: 1024,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.ARM64,
      },
    });

    taskDefinition.addContainer("Container", {
      image: ecs.ContainerImage.fromAsset(path.join(__dirname, '../../stfrontend')),
      portMappings: [{ containerPort: 8501 }],
    });

    taskDefinition.addToTaskRolePolicy(new iam.PolicyStatement({
      actions: ['s3:*'],
      resources: ['*'],
    }));

    taskDefinition.addToTaskRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:*'],
      resources: ['*']
    }))

    new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'FargateService', {
      cluster: cluster,
      taskDefinition: taskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      publicLoadBalancer: true,
      listenerPort: 80
    });

    const prime_lambda = new lambda.DockerImageFunction(this, 'PrimeLambda', {
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../../lambda/prime')),
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      architecture: lambda.Architecture.ARM_64,
    });

    new apigw.LambdaRestApi(this, 'PrimeAPI', {
      handler: prime_lambda,
    });

    const table = new ddb.Table(this, 'Invoices', {
      partitionKey: { name: 'invoice_id', type: ddb.AttributeType.STRING },
      billingMode: ddb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
    });

    table.addGlobalSecondaryIndex({
      indexName: 'user-index',
      partitionKey: { name: 'user_id', type: ddb.AttributeType.STRING },
      sortKey: { name: 'created_time', type: ddb.AttributeType.NUMBER },
    });

    const invoice_api = new lambda.DockerImageFunction(this, 'InvoiceLambda', {
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../../lambda/invoice_api')),
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        'TABLE_NAME': table.tableName,
      }
    });

    table.grantReadWriteData(invoice_api);

    new apigw.LambdaRestApi(this, 'InvoiceAPI', {
      handler: invoice_api,
    });
  }
}
