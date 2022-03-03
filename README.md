# kube-ecr-cleanup
Clean up AWS ECR images based on a git repo

- this is out-of-date, a newer version exists in a private repo. I'll pull that out some time

# Future Work
* Fill out this readme
* Package with Helm
* Make the script actually fail when things go wrong
    * `os.system` currently just quietly fails
* Add lint workflow (since this is python now)
* Add unit tests
