// output to .drone.yml (which drone really reads)
// jsonnet .drone.jsonnet | jq . | yq -P - > .drone.yml


local VALUES = {
  PROJECT_NAME:             "koala",
  DOCKERHUB_USER:           "osdp25w",
  DOCKERHUB_IMAGE:          "osdp25w/koala",
  K8S_DEPLOYMENT_NAME:      "koala",
  K8S_DEPLOYMENT_NAMESPACE: "koala",
  CONTAINER_NAME:           "koala",
  BRANCH:                   "master",
};



local SECRET = {
  K8S_SERVER:           { from_secret: "K8S_SERVER" },
  K8S_TOKEN:            { from_secret: "K8S_TOKEN" },
  K8S_CA:               { from_secret: "K8S_CA" },
  DOCKER_USERNAME:      { from_secret: "DOCKER_USERNAME_osdp25w" },
  DOCKER_PASSWORD:      { from_secret: "DOCKER_PASSWORD_osdp25w" },
};


// local CELERY_DEPLOYMENTS = [
//   "%s-celery-playlog" % VALUES.K8S_DEPLOYMENT_NAME,
//   "%s-celery-beat" % VALUES.K8S_DEPLOYMENT_NAME,
// ];


local migration_chack_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "koala-migration-check",
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
    repo: "Osdp25w-koala",
  },
  trigger: {
    event: ["pull_request"],
  },
  steps: [
    {
      name:  "migration-dry-run",
      image: "python:3.10.13-slim",
      environment:{
        DJANGO_SECRET_KEY: "MIGRATION_CHECK_PIPELINE_SUPER_SECRET",
        GENERIC_SECRET_SIGNING_KEY: "l-HUGJOVf2tXV6zajZCKNgo43DKNIbq2cRbjTnwcuTs=",
        LOGIN_SECRET_SIGNING_KEY: "l-HUGJOVf2tXV6zajZCKNgo43DKNIbq2cRbjTnwcuTs=",
      },
      commands: [
        "pip install -r requirements.txt || exit 1",
        "python manage.py check || exit 1",
        "python manage.py makemigrations --dry-run --check",
      ],
    },
  ],
};

local test_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "koala-test",
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
    repo: "Osdp25w-koala",
  },
  trigger: {
    event:  ["push"],
    branch: [ VALUES.BRANCH ],
  },
  services: [
    {
      name: "koala-test-db",
      image: "postgres:14-alpine",
      environment: {
        POSTGRES_USER: "koala-test",
        POSTGRES_PASSWORD: "koala-test",
        POSTGRES_DB: "koala-test",
      },
    },
    {
      name: "koala-test-redis",
      image: "redis:7.4.2",
    },
  ],
  steps: [
    {
      name: "test",
      image: "python:3.10.13-slim",
      environment: {
        ENV: "local",
        DJANGO_SECRET_KEY: "TEST_PIPELINE_SUPER_SECRET",
        GENERIC_SECRET_SIGNING_KEY: "l-HUGJOVf2tXV6zajZCKNgo43DKNIbq2cRbjTnwcuTs=",
        LOGIN_SECRET_SIGNING_KEY: "l-HUGJOVf2tXV6zajZCKNgo43DKNIbq2cRbjTnwcuTs=",
        POSTGRES_HOST: "koala-test-db",
        POSTGRES_USER: "koala-test",
        POSTGRES_PASSWORD: "koala-test",
        POSTGRES_DB: "koala-test",
        POSTGRES_PORT: "5432",
        REDIS_HOST: "koala-test-redis",
        REDIS_PORT: "6379",
      },
      commands: [
        "echo '🔧 Installing system dependencies...'",
        "apt-get update && apt-get install -y postgresql-client redis-tools",
        "echo '📦 Installing Python dependencies...'",
        "pip install -r requirements.txt",
        "echo '⏳ Waiting for services to be ready...'",
        "until pg_isready -h koala-test-db -p 5432 -U koala-test; do echo 'PostgreSQL not ready, waiting...'; sleep 2; done",
        "until redis-cli -h koala-test-redis -p 6379 ping | grep -q PONG; do echo 'Redis not ready, waiting...'; sleep 2; done",
        "echo '✅ All services are ready!'",
        "echo '🔍 Debugging information:'",
        "env | grep -E '(POSTGRES|REDIS|DJANGO)' | sort",
        "echo '🔌 Testing database connection...'",
        "python -c \"import os; import psycopg2; conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), database=os.getenv('POSTGRES_DB'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'), port=os.getenv('POSTGRES_PORT')); print('✅ Database connection successful'); conn.close()\"",
        "echo '🔍 Running Django system check...'",
        "python manage.py check || exit 1",
        "echo '✅ Django system check passed!'",
        "echo '📊 Running migrations...'",
        "python manage.py migrate --verbosity=2 || exit 1",
        "echo '✅ Migrations completed!'",
        "echo '🧪 Testing Redis connection...'",
        "python -c \"import redis; r = redis.Redis(host='koala-test-redis', port=6379); r.ping(); print('✅ Redis connection successful')\"",
        "echo '🔍 Debugging database permissions and sessions table...'",
        "PGPASSWORD=koala-test psql -h koala-test-db -U koala-test -d koala-test -c \"SELECT version();\" || echo 'Basic DB connection failed'",
        "PGPASSWORD=koala-test psql -h koala-test-db -U koala-test -d koala-test -c \"CREATE TABLE test_permissions (id SERIAL PRIMARY KEY, test_col TEXT); DROP TABLE test_permissions;\" || echo 'CREATE TABLE permission denied'",
        "echo '🔍 Testing sessions table creation specifically...'",
        "PGPASSWORD=koala-test psql -h koala-test-db -U koala-test -d koala-test -c \"CREATE TABLE IF NOT EXISTS django_session (session_key VARCHAR(40) PRIMARY KEY, session_data TEXT, expire_date TIMESTAMP); SELECT COUNT(*) FROM django_session;\" || echo 'Sessions table creation failed'",
        "echo '🔧 Trying test with standard PostgreSQL backend...'",
        "DJANGO_DATABASE_ENGINE='django.db.backends.postgresql' timeout 300 python manage.py test --noinput --verbosity=3 account.tests.test_auth.AuthViewTest.test_login_invalid_credentials || echo '❌ Standard backend test failed'",
        "echo '🔧 Final test attempt with all optimizations...'",
        "timeout 600 python manage.py test --noinput --verbosity=1 --parallel=1 --keepdb || exit 1",
        "echo '🎉 Tests completed!'",
      ],
    },
  ],
};

local deploy_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "koala-deploy",
  depends_on: ["koala-test"],
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
      repo: "Osdp25w-koala",
  },
  trigger: {
    event:  ["push"],
    branch: [ VALUES.BRANCH ],
  },
  steps: [
    {
      name:  "build and push docker image",
      image: "plugins/docker",
      settings: {
        repo:  VALUES.DOCKERHUB_IMAGE,
        tags: ["latest", "${DRONE_COMMIT_SHA}"],
        username: SECRET.DOCKER_USERNAME,
        password: SECRET.DOCKER_PASSWORD,
      },
    },
    {
      name:  "deploy to k8s",
      image: "sinlead/drone-kubectl",
      settings: {
        kubernetes_server: SECRET.K8S_SERVER,
        kubernetes_token:  SECRET.K8S_TOKEN,
        kubernetes_cert:   SECRET.K8S_CA,
        namespace: VALUES.K8S_DEPLOYMENT_NAMESPACE,
        startTimeout: 240
      },
      commands: [
        std.format(
          "kubectl set image deployment/%s %s=%s:${DRONE_COMMIT_SHA} --namespace=%s || exit 1",
          [VALUES.K8S_DEPLOYMENT_NAME, VALUES.CONTAINER_NAME, VALUES.DOCKERHUB_IMAGE, VALUES.K8S_DEPLOYMENT_NAMESPACE]
        ),
        std.format(
          "echo 'Waiting for deployment to become ready...'; kubectl rollout status deployment/%s --namespace=%s --timeout=120s || (echo '❌ Deployment failed readiness check'; exit 1)",
          [VALUES.K8S_DEPLOYMENT_NAME, VALUES.K8S_DEPLOYMENT_NAMESPACE]
        ),
        std.format(
          "echo '✅ Deployment %s is successfully rolled out and ready.'",
          [VALUES.K8S_DEPLOYMENT_NAME]
        )
      ]
    },
  ],
};

std.manifestYamlDoc(migration_chack_pipeline) + "\n---\n" + std.manifestYamlDoc(test_pipeline) + "\n---\n" + std.manifestYamlDoc(deploy_pipeline)
