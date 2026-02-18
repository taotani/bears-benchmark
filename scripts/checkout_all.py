import os
import json
import argparse
import subprocess
import sys

# Add scripts/ to the path to import config
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))
from config import *

def main():
    parser = argparse.ArgumentParser(description='Script to check out all bugs from Bears')
    parser.add_argument('--workspace', help='The path to a folder to store the checked out bugs', required=False, metavar='')
    parser.add_argument('--limit', help='Limit the number of bugs to check out (for testing)', type=int, default=0, required=False, metavar='')
    args = parser.parse_args()

    # Determine workspace path
    workspace = args.workspace
    if workspace is None:
        workspace = os.path.join(BEARS_PATH, "workspace")

    if not os.path.isabs(workspace):
        workspace = os.path.abspath(workspace)

    os.makedirs(workspace, exist_ok=True)

    # Load bugs
    bugs = []
    bears_bugs_path = os.path.join(BEARS_PATH, BEARS_BUGS)
    if os.path.exists(bears_bugs_path):
        with open(bears_bugs_path, 'r') as f:
            try:
                bugs = json.load(f)
            except Exception as e:
                print("Error loading bugs: %s" % e)
                sys.exit(1)
    else:
        print("Bugs file not found: %s" % bears_bugs_path)
        sys.exit(1)

    print("Found %d bugs in %s" % (len(bugs), BEARS_BUGS))
    
    # Get basename of workspace for exclusion
    workspace_basename = os.path.basename(workspace)
    
    # Ensure we return to master even if interrupted
    try:
        for i, bug in enumerate(bugs):
            if args.limit > 0 and i >= args.limit:
                print("Reached limit of %d bugs." % args.limit)
                break

            bug_id = bug['bugId']
            bug_branch = bug['bugBranch']
            bug_folder_path = os.path.join(workspace, bug_id)

            if os.path.isdir(bug_folder_path):
                print("[%d/%d] %s already checked out, skipping." % (i+1, len(bugs), bug_id))
                continue

            print("[%d/%d] Checking out %s..." % (i+1, len(bugs), bug_id))

            # 1. Checkout the branch
            cmd = "cd %s; git reset --hard HEAD > /dev/null 2>&1; git checkout %s --quiet;" % (BEARS_PATH, bug_branch)
            subprocess.call(cmd, shell=True)

            # 2. Find buggy commit
            try:
                cmd = "cd %s; git log --format=format:%%H --grep='Changes in the tests' -n 1;" % BEARS_PATH
                buggy_commit = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
                
                if not buggy_commit:
                    print("  Warning: Buggy commit not found for %s" % bug_id)
                    continue

                cmd = "cd %s; git checkout %s --quiet;" % (BEARS_PATH, buggy_commit)
                subprocess.call(cmd, shell=True)

                # 3. Copy files
                os.makedirs(bug_folder_path, exist_ok=True)
                
                exclude_args = "-not -name .git"
                # If workspace is inside repo, exclude it
                if workspace.startswith(BEARS_PATH):
                     exclude_args += " -not -name %s" % workspace_basename
                
                # Also exclude the default 'workspace' if it's different, just to be clean
                if workspace_basename != "workspace":
                     exclude_args += " -not -name workspace"
                
                # Copy files
                cmd = "cd %s; find . -mindepth 1 -maxdepth 1 %s -print0 | xargs -0 -I{} cp -r {} %s/;" % (BEARS_PATH, exclude_args, bug_folder_path)
                subprocess.call(cmd, shell=True)

            except subprocess.CalledProcessError as e:
                print("  Error finding/checking out commit for %s: %s" % (bug_id, e))
            except Exception as e:
                print("  Error processing %s: %s" % (bug_id, e))
                
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Returning to master...")
        cmd = "cd %s; git reset --hard HEAD > /dev/null 2>&1; git checkout master --quiet;" % BEARS_PATH
        subprocess.call(cmd, shell=True)
        print("Done. Workspace is at: %s" % workspace)

if __name__ == "__main__":
    main()
