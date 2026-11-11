//! Keep untracked scratch files out of commit checks without losing project-wide analysis.

use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin;
use predicates::prelude::*;
use std::fs;
use std::path::Path;

fn git(root: &Path, args: &[&str]) {
    let output = std::process::Command::new("git")
        .current_dir(root)
        .args(args)
        .output()
        .expect("git should run");
    assert!(output.status.success(), "{output:?}");
}

#[test]
fn tracked_mode_ignores_scratch_files_until_they_are_added_to_git() {
    let root = assert_fs::TempDir::new().expect("test dir should be created");
    git(root.path(), &["init", "-q"]);
    fs::write(root.path().join("tracked space\nfile.py"), "value = 1\n")
        .expect("source should be writable");
    fs::write(root.path().join("scratch.py"), "getattr(config, name)\n")
        .expect("source should be writable");
    git(root.path(), &["add", "tracked space\nfile.py"]);

    for extra in [vec![], vec!["--include-all"]] {
        Command::new(cargo_bin!("scb-check"))
            .current_dir(root.path())
            .args(["check", "--scope", "tracked", "--report", "."])
            .args(extra)
            .assert()
            .success()
            .stdout(predicate::str::contains("\"files_scanned\":1"));
    }
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "."])
        .assert()
        .code(1)
        .stdout(predicate::str::contains("error[no-reflection]"));

    git(root.path(), &["add", "scratch.py"]);
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "--gate", "findings", "."])
        .assert()
        .code(1)
        .stdout(predicate::str::contains("error[no-reflection]"));
}

#[test]
fn tracked_mode_respects_scope_exclusions_and_working_tree_deletions() {
    let root = assert_fs::TempDir::new().expect("test dir should be created");
    git(root.path(), &["init", "-q"]);
    fs::create_dir(root.path().join("src")).expect("source dir should be created");
    fs::create_dir(root.path().join("target")).expect("build dir should be created");
    for file in [
        "outside.py",
        "src/keep.py",
        "src/deleted.py",
        "src/skip.py",
        "target/build.py",
    ] {
        fs::write(root.path().join(file), "value = 1\n").expect("source should be writable");
    }
    git(root.path(), &["add", "."]);
    fs::remove_file(root.path().join("src/deleted.py")).expect("source should be removable");
    fs::write(root.path().join(".gitignore"), "src/keep.py\n")
        .expect("gitignore should be writable");
    fs::write(
        root.path().join("scb-check.toml"),
        "exclude = ['src/skip.py']\n",
    )
    .expect("config should be writable");

    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "--report", "src"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"files_scanned\":1"));
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "--report", "."])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"files_scanned\":2"));
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "--report", "src/keep.py"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"files_scanned\":1"));
}

#[test]
fn tracked_mode_keeps_cross_file_clone_detection() {
    let root = assert_fs::TempDir::new().expect("test dir should be created");
    git(root.path(), &["init", "-q"]);
    for file in ["first.py", "second.py"] {
        fs::write(
            root.path().join(file),
            "def calculate(value):\n    result = value + 1\n    return result * 2\n",
        )
        .expect("source should be writable");
    }
    git(root.path(), &["add", "."]);
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "--gate", "findings", "."])
        .assert()
        .code(1)
        .stdout(predicate::str::contains("duplicate-structure"));
}

#[test]
fn tracked_mode_requires_git_but_allows_an_empty_repository() {
    let root = assert_fs::TempDir::new().expect("test dir should be created");
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "."])
        .assert()
        .code(2)
        .stderr(predicate::str::contains("failed to list Git-tracked files"));
    git(root.path(), &["init", "-q"]);
    fs::write(root.path().join("scratch.py"), "getattr(config, name)\n")
        .expect("source should be writable");
    Command::new(cargo_bin!("scb-check"))
        .current_dir(root.path())
        .args(["check", "--scope", "tracked", "."])
        .assert()
        .success()
        .stdout("");
}
