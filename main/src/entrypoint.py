"""Entrypoint for ecr cleanup."""

import os
from typing import Dict, List

import boto3


def extract_env() -> Dict[str, str]:
    """Extract necessary data from env vars."""
    expected = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "ECR_REPOSITORY_NAME",
        "CONTAINER_NAMES",
        "GITHUB_REPOSITORY",
        "GITHUB_DEPLOY_KEY_PRI_64",
        "COMMITS_PER_BRANCH",
    ]
    env: Dict[str, str] = {}
    for var_name in expected:
        val = os.getenv(var_name)
        if val is None or not val:  # Disallow empty strings
            raise Exception(f"No value for {var_name}")
        env[var_name] = val
    return env


def prepare_git(deploy_key_64: str) -> None:
    """Prepare to access repository."""
    # Prepare folder
    if not os.path.exists("/root/.ssh"):
        os.mkdir("/root/.ssh")

    # Save deploy key to file
    with open("key_file.txt", "w+") as key_file:
        key_file.write(deploy_key_64)

    # Input into file
    os.system("cat key_file.txt | base64 -d > /root/.ssh/id_rsa")
    os.system("chmod 600 /root/.ssh/id_rsa")

    # Get rid of key file
    os.remove("key_file.txt")

    # Validate
    out = os.system("ssh -oStrictHostKeyChecking=no -T git@github.com")
    if out not in [0, 256]:
        raise Exception(f"Git authentication failed with status {out}")


def get_tag_whitelist(
    github_repository: str, container_names: List[str], commits_per_branch: int
) -> List[str]:
    """Use git to get a list of tags we'll whitelist."""
    # Initialize whitelist with anything specific
    whitelist = []
    for container_name in container_names:
        whitelist.append(f"latest-{container_name}")

    # Git clone repo
    os.mkdir("/root/cloned_repo")
    os.chdir("/root/cloned_repo")
    os.system(f"git clone git@github.com:{github_repository}.git")
    os.chdir(f"{github_repository.split('/')[-1]}")

    # Get active branches
    output = os.popen('git branch -r --format="%(refname)"').read()
    branches = [fullref.split("/")[-1] for fullref in output.split("\n") if fullref]
    if "HEAD" in branches:
        branches.remove("HEAD")

    for branch in branches:
        # Get last n commits on branch
        output = os.popen(
            f'git log -{commits_per_branch} origin/{branch} --format="%H"'
        ).read()
        commits = [commit for commit in output.split("\n") if commit]

        # Add to output
        for commit in commits:
            for container_name in container_names:
                whitelist.append(f"{branch}-{commit}-{container_name}")

    os.chdir("/root")
    return whitelist


def prepare_aws(access_key_id: str, secret_access_key: str, region: str) -> None:
    """Prepare AWS with credentials."""
    # Prepare folder
    if not os.path.exists("/root/.aws"):
        os.mkdir("/root/.aws")

    # Input into file
    lines = [
        "[default]",
        f"aws_access_key_id = {access_key_id}",
        f"aws_secret_access_key = {secret_access_key}",
        f"region={region}",
    ]
    with open("/root/.aws/creds", "w+") as cred_file:
        cred_file.write("\n".join(lines))


def get_images(ecr_client, repository_name: str) -> List[Dict]:
    """Get all images from a repository."""
    return ecr_client.list_images(repositoryName=repository_name)["imageIds"]


def get_bad_images(images: List[Dict], tag_whitelist: List[str]) -> List[Dict]:
    """Filter a list of images for non-whitelisted tags or no tags."""
    bad_images = []
    for image in images:
        image_tag = image.get("imageTag", "")
        image_digest = image.get("imageDigest", "")
        if not image_tag and not image_digest:
            print("Found entirely blank image")
        elif not image_tag:
            bad_images.append({"imageDigest": image_digest})
        elif image_tag not in tag_whitelist:
            bad_images.append({"imageTag": image_tag})
    return bad_images


def delete_images(ecr_client, repository_name: str, bad_images: List[Dict]) -> None:
    """Delete images from a list."""
    ecr_client.batch_delete_image(repositoryName=repository_name, imageIds=bad_images)


def main():
    """Run the entrypoint script."""
    env = extract_env()
    prepare_git(deploy_key_64=env["GITHUB_DEPLOY_KEY_PRI_64"])
    container_names = [name.strip() for name in env["CONTAINER_NAMES"].split(",")]
    tag_whitelist = get_tag_whitelist(
        github_repository=env["GITHUB_REPOSITORY"],
        container_names=container_names,
        commits_per_branch=env["COMMITS_PER_BRANCH"],
    )
    prepare_aws(
        access_key_id=env["AWS_ACCESS_KEY_ID"],
        secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region=env["AWS_DEFAULT_REGION"],
    )
    ecr_client = boto3.client("ecr")
    images = get_images(
        ecr_client=ecr_client, repository_name=env["ECR_REPOSITORY_NAME"]
    )
    bad_tags = get_bad_images(images=images, tag_whitelist=tag_whitelist)
    delete_images(
        ecr_client=ecr_client,
        repository_name=env["ECR_REPOSITORY_NAME"],
        bad_tags=bad_tags,
    )


if __name__ == "__main__":
    main()
