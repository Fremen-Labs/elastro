import os
import subprocess

def main():
    workspace = "/Users/jonathandoughty/clients/fremenlabs"
    elastro_dir = "/Users/jonathandoughty/clients/fremenlabs/elastic/elastic-github/elastro-feature-async-client"
    python_bin = os.path.join(elastro_dir, ".venv/bin/python3")
    cli_path = os.path.join(elastro_dir, "elastro/cli/cli.py")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = elastro_dir

    repos = []
    print(f"Scanning {workspace} for git repositories...")
    
    for root, dirs, files in os.walk(workspace):
        # Skip node_modules and similar massive directories to speed up traversal
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if ".venv" in dirs:
            dirs.remove(".venv")
        if "venv" in dirs:
            dirs.remove("venv")
            
        if '.git' in dirs:
            repos.append(root)
            dirs.remove('.git')  # don't recurse into .git

    print(f"Found {len(repos)} repositories to ingest. Starting batch ingestion...\n")

    for repo in repos:
        print(f"============================================================")
        print(f"🚀 Ingesting: {repo}")
        print(f"============================================================")
        try:
            cmd = [python_bin, cli_path, "rag", "ingest", repo]
            result = subprocess.run(
                cmd, 
                env=env, 
                cwd=elastro_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Print just the tail end or success message
                lines = result.stdout.strip().split('\n')
                print('\n'.join(lines[-4:]))
            else:
                print(f"❌ Failed to ingest {repo}. Exit code: {result.returncode}")
                print(result.stderr)
        except Exception as e:
            print(f"❌ Exception running ingest on {repo}: {e}")
            
if __name__ == "__main__":
    main()
