#!/usr/bin/env python3
"""Validate isolation and required settings for independent deployments."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.independent.yml"
REQUIRED = {
    "COMPOSE_PROJECT_NAME",
    "ODOO_PORT",
    "TCSI_ODOO_IMAGE",
    "PG_ADMIN_USER",
    "PG_ADMIN_PASSWORD",
    "PGUSER",
    "PGPASSWORD",
    "PGDATABASE",
    "TCSI_ADMIN_LOGIN",
    "TCSI_ADMIN_PASSWORD",
    "TCSI_MASTER_PASSWORD",
}


def deployment_env(project, port):
    env = os.environ.copy()
    for name in REQUIRED:
        env.pop(name, None)
    env.update(
        {
            "COMPOSE_PROJECT_NAME": project,
            "ODOO_PORT": str(port),
            "TCSI_ODOO_IMAGE": "registry.example.invalid/accounting@sha256:" + "a" * 64,
            "PG_ADMIN_USER": f"{project}_admin",
            "PG_ADMIN_PASSWORD": f"{project}-database-admin-secret",
            "PGUSER": f"{project}_odoo",
            "PGPASSWORD": f"{project}-application-database-secret",
            "PGDATABASE": f"{project}_accounting",
            "TCSI_ADMIN_LOGIN": f"admin@{project}.invalid",
            "TCSI_ADMIN_PASSWORD": f"{project}-initial-admin-password-long-enough",
            "TCSI_MASTER_PASSWORD": f"{project}-master-password-long-enough",
        }
    )
    return env


def compose(env, *arguments, timeout=300):
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def compose_config(env):
    return compose(env, "config", "--format", "json")


class IndependentDeploymentStaticTest(unittest.TestCase):
    def test_example_leaves_release_identity_and_credentials_unset(self):
        example = ROOT / "config" / "independent.env.example"
        assignments = {}
        for raw_line in example.read_text().splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                assignments[name] = value

        unset_required = {
            "TCSI_ODOO_IMAGE",
            "PG_ADMIN_PASSWORD",
            "PGPASSWORD",
            "TCSI_ADMIN_LOGIN",
            "TCSI_ADMIN_PASSWORD",
            "TCSI_MASTER_PASSWORD",
        }
        self.assertTrue(unset_required.issubset(assignments))
        self.assertTrue(all(assignments[name] == "" for name in unset_required))

        compose_text = COMPOSE_FILE.read_text()
        for name in unset_required:
            with self.subTest(name=name):
                self.assertIn(f"${{{name}:?", compose_text)

    def test_recovery_runbook_arms_restart_and_records_live_image(self):
        runbook = (ROOT / "docs" / "platform-deployment.md").read_text()
        image_check = "if [ \"$CONFIG_IMAGE_ID\" != \"$LIVE_IMAGE_ID\" ]; then"
        arm_restart = "\nsource_stopped=1\n"
        stop_odoo = "\n\"${source_compose[@]}\" stop odoo\n"

        self.assertIn(image_check, runbook)
        self.assertLess(runbook.index(image_check), runbook.index(arm_restart))
        self.assertLess(runbook.index(arm_restart), runbook.index(stop_odoo))
        self.assertIn(
            'printf \'%s\\n\' "$LIVE_IMAGE_ID" > "$partial/image-id.txt"',
            runbook,
        )


class IndependentDeploymentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("docker") is None:
            raise unittest.SkipTest("docker compose is required")
        probe = subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode:
            raise unittest.SkipTest("docker compose is required")

    def config(self, project="firmone", port=18069):
        result = compose_config(deployment_env(project, port))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_every_identity_and_credential_is_mandatory(self):
        for missing in sorted(REQUIRED):
            with self.subTest(missing=missing):
                env = deployment_env("firmone", 18069)
                env.pop(missing)
                result = compose_config(env)
                self.assertNotEqual(result.returncode, 0, missing)

    def test_two_projects_get_distinct_resources(self):
        first = self.config("firmone", 18069)
        second = self.config("firmtwo", 28069)

        self.assertEqual(first["name"], "firmone")
        self.assertEqual(second["name"], "firmtwo")
        for resource_type in ("networks", "volumes"):
            first_names = {item["name"] for item in first[resource_type].values()}
            second_names = {item["name"] for item in second[resource_type].values()}
            self.assertTrue(first_names.isdisjoint(second_names))
            self.assertTrue(all(name.startswith("firmone_") for name in first_names))
            self.assertTrue(all(name.startswith("firmtwo_") for name in second_names))

    def test_database_is_private_and_app_is_loopback_only(self):
        services = self.config()["services"]
        self.assertNotIn("ports", services["db"])
        self.assertNotIn("ports", services["db-init"])
        self.assertIn("-h 127.0.0.1", services["db"]["healthcheck"]["test"][1])
        self.assertEqual(
            services["odoo"]["ports"],
            [
                {
                    "mode": "ingress",
                    "target": 8069,
                    "published": "18069",
                    "protocol": "tcp",
                    "host_ip": "127.0.0.1",
                }
            ],
        )

    def test_odoo_uses_single_database_launcher_and_app_role(self):
        services = self.config()["services"]
        odoo = services["odoo"]
        self.assertEqual(odoo["command"], ["python3", "/opt/tcsi/cloud_start.py"])
        self.assertEqual(odoo["environment"]["PGUSER"], "firmone_odoo")
        self.assertNotIn("PG_ADMIN_PASSWORD", odoo["environment"])
        self.assertEqual(odoo["environment"]["TCSI_SETUP_TOKEN_SHA256"], "")
        self.assertEqual(
            odoo["depends_on"]["db-init"]["condition"],
            "service_completed_successfully",
        )

    def test_no_fixed_container_or_resource_names(self):
        config = self.config()
        self.assertTrue(all("container_name" not in service for service in config["services"].values()))
        for resources in (config["networks"], config["volumes"]):
            self.assertTrue(all(item["name"].startswith("firmone_") for item in resources.values()))

    def test_database_bootstrap_enforces_least_privilege_and_secret_length(self):
        project = f"tcsibootstrap{os.getpid()}"
        env = deployment_env(project, 38069)
        try:
            started = compose(env, "up", "-d", "--wait", "db")
            self.assertEqual(started.returncode, 0, started.stderr)

            initialized = compose(env, "run", "--rm", "--no-deps", "db-init")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            role = compose(
                env,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                env["PG_ADMIN_USER"],
                "-d",
                "postgres",
                "-At",
                "-F",
                "|",
                "-c",
                (
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                    "rolbypassrls FROM pg_roles WHERE rolname = "
                    f"'{env['PGUSER']}'"
                ),
            )
            self.assertEqual(role.returncode, 0, role.stderr)
            self.assertEqual(role.stdout.strip(), "f|f|f|f|f")

            elevated = compose(
                env,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                env["PG_ADMIN_USER"],
                "-d",
                "postgres",
                "-c",
                f'ALTER ROLE "{env["PGUSER"]}" CREATEDB CREATEROLE BYPASSRLS',
            )
            self.assertEqual(elevated.returncode, 0, elevated.stderr)

            rotated = env.copy()
            rotated["PGPASSWORD"] = f"{project}-rotated-application-password"
            reconciled = compose(rotated, "run", "--rm", "--no-deps", "db-init")
            self.assertEqual(reconciled.returncode, 0, reconciled.stderr)

            role = compose(
                rotated,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                rotated["PG_ADMIN_USER"],
                "-d",
                "postgres",
                "-At",
                "-F",
                "|",
                "-c",
                (
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                    "rolbypassrls FROM pg_roles WHERE rolname = "
                    f"'{rotated['PGUSER']}'"
                ),
            )
            self.assertEqual(role.returncode, 0, role.stderr)
            self.assertEqual(role.stdout.strip(), "f|f|f|f|f")

            login = compose(
                rotated,
                "exec",
                "-T",
                "-e",
                f"PGPASSWORD={rotated['PGPASSWORD']}",
                "db",
                "psql",
                "-h",
                "127.0.0.1",
                "-U",
                rotated["PGUSER"],
                "-d",
                rotated["PGDATABASE"],
                "-Atc",
                "SELECT current_user",
            )
            self.assertEqual(login.returncode, 0, login.stderr)
            self.assertEqual(login.stdout.strip(), rotated["PGUSER"])

            invalid = env.copy()
            invalid["PGPASSWORD"] = "too-short"
            rejected = compose(invalid, "run", "--rm", "--no-deps", "db-init")
            self.assertNotEqual(rejected.returncode, 0)

            reused = env.copy()
            reused["PGPASSWORD"] = reused["PG_ADMIN_PASSWORD"]
            rejected = compose(reused, "run", "--rm", "--no-deps", "db-init")
            self.assertNotEqual(rejected.returncode, 0)

            too_long = env.copy()
            too_long["PGUSER"] = "a" * 64
            rejected = compose(too_long, "run", "--rm", "--no-deps", "db-init")
            self.assertNotEqual(rejected.returncode, 0)
        finally:
            compose(env, "down", "--volumes", "--remove-orphans")

    def test_database_bootstrap_uses_linux_line_endings(self):
        script = (ROOT / "docker" / "postgres" / "init-independent.sh").read_bytes()
        self.assertNotIn(b"\r", script)
        attributes = (ROOT / ".gitattributes").read_text()
        self.assertIn("docker/postgres/*.sh text eol=lf", attributes.splitlines())


if __name__ == "__main__":
    unittest.main()
