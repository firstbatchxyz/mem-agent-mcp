import os, shutil, json
import argparse

# Constants
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FILTERS_PATH = os.path.join(REPO_ROOT, ".filters")

def add_filters() -> None:
    """
    In an input loop, add filter to .filters 
    given by the user.
    """
    try:
        with open(FILTERS_PATH, "a") as f:
            print("Enter a filter or type quit() to exit")
            user_input = input("-: ").strip()
            while user_input.lower() != "quit()":
                f.write("- " + user_input + "\n")
                user_input = input("-: ").strip()
    except Exception as e:
        print(f"Error adding filters: {e}")

def reset_filters() -> None:
    """
    Reset the filters file by deleting it and 
    creating a new one.
    """
    try:
        os.remove(FILTERS_PATH)
        with open(FILTERS_PATH, "w") as f:
            f.write("")
    except Exception as e:
        print(f"Error resetting filters: {e}")

def main() -> None:
    # Add commandline args to determine the action
    parser = argparse.ArgumentParser(description="Filters script")
    parser.add_argument("--add", action="store_true", help="Add filters")
    parser.add_argument("--reset", action="store_true", help="Reset filters")
    args = parser.parse_args()
    
    if args.add:
        add_filters()
    elif args.reset:
        reset_filters()
    else:
        print("No action specified. Use --add or --reset")

if __name__ == "__main__":
    main()