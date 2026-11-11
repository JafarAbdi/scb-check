//! Verify house-rule findings and suppressions through the CLI used by pre-commit.

use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin;
use predicates::prelude::*;
use std::fs;

#[test]
fn house_rules_gate_commits_and_support_source_and_config_suppression() {
    let cases = [
        ("explicit-dtype", "np.zeros(3, dtype=np.float64)\n"),
        ("no-reflection", "getattr(config, name)\n"),
        (
            "no-import-fallback",
            "try:\n    import tomllib\nexcept ImportError:\n    import tomli as tomllib\n",
        ),
        ("no-python-subprocess", "subprocess.run(['tool'])\n"),
        ("section-banner-comment", "# ---- Helpers ----\n"),
    ];
    for (rule_id, source) in cases {
        let root = assert_fs::TempDir::new().expect("test dir should be created");
        let file = root.path().join("sample.py");
        let config = root.path().join("scb-check.toml");
        fs::write(&file, source).expect("source should be writable");
        fs::write(&config, "").expect("config should be writable");

        Command::new(cargo_bin!("scb-check"))
            .current_dir(root.path())
            .args(["check", "--gate", "findings", "."])
            .assert()
            .code(1)
            .stdout(predicate::str::contains(format!("error[{rule_id}]")));

        Command::new(cargo_bin!("scb-check"))
            .args(["rule", rule_id])
            .assert()
            .success()
            .stdout(predicate::str::contains(format!("id: {rule_id}")));

        fs::write(&config, format!("disable-rules = [\"{rule_id}\"]\n"))
            .expect("config should be writable");
        Command::new(cargo_bin!("scb-check"))
            .current_dir(root.path())
            .args(["check", "--gate", "findings", "."])
            .assert()
            .success()
            .stdout("");

        if rule_id != "section-banner-comment" {
            fs::write(&config, "").expect("config should be writable");
            fs::write(
                &file,
                format!("# scbc ignore[{rule_id}] justified\n{source}"),
            )
            .expect("source should be writable");
            Command::new(cargo_bin!("scb-check"))
                .current_dir(root.path())
                .args(["check", "--gate", "findings", "."])
                .assert()
                .success()
                .stdout("");
            Command::new(cargo_bin!("scb-check"))
                .current_dir(root.path())
                .args(["check", "--gate", "findings", "--include-all", "."])
                .assert()
                .code(1)
                .stdout(predicate::str::contains(format!("error[{rule_id}]")));
        }
    }
}
