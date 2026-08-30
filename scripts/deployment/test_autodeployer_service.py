#!/usr/bin/env python3
"""Contract tests for the Linux autodeployer unit."""

import unittest
from pathlib import Path


SERVICE = Path(__file__).parents[2] / "deploy" / "ada-deployer.service"


class AutodeployerServiceTest(unittest.TestCase):
    def test_installer_can_create_missing_env_file(self):
        installer = (Path(__file__).with_name("install-autodeployer.sh")).read_text()

        self.assertIn('install -o "${ada_user}" -g "${ada_group}" -m 0600', installer)
        self.assertIn('template="${project_dir}/deploy/.env.example"', installer)
        self.assertIn('set_env_value "ADA_DATA_DIR" "${data_dir}"', installer)
        self.assertIn('set_env_value "ADA_GDRIVE_PATH" "${data_dir}"', installer)
        self.assertIn('install -o "${ada_user}" -g "${ada_group}" -m 0660 /dev/null', installer)
        self.assertIn('chown "${ada_user}:${ada_group}" "${env_file}"', installer)
        self.assertIn('chmod 0600 "${env_file}"', installer)

    def test_service_is_renderable_and_restarts_deployer(self):
        content = SERVICE.read_text()

        for placeholder in (
            "@ADA_DIR@",
            "@ADA_ENV_FILE@",
            "@ADA_USER@",
            "@ADA_GROUP@",
        ):
            self.assertIn(placeholder, content)

        self.assertIn("After=docker.service network-online.target", content)
        self.assertIn("ExecStartPre=/usr/bin/docker info", content)
        self.assertIn("User=@ADA_USER@", content)
        self.assertIn("Group=@ADA_GROUP@", content)
        self.assertIn("SupplementaryGroups=docker", content)
        self.assertIn("Environment=DOCKER_CONFIG=/tmp/ada-deployer-docker-config", content)
        self.assertIn("ExecStartPre=/usr/bin/mkdir -p /tmp/ada-deployer-home /tmp/ada-deployer-docker-config", content)
        self.assertIn("Restart=always", content)
        self.assertIn("WantedBy=multi-user.target", content)


if __name__ == "__main__":
    unittest.main()
