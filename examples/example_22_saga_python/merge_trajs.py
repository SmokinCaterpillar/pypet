import os

from the_task import FunctionParameter

from pypet import merge_all_in_folder


def main():
    """Simply merge all trajectories in the working directory"""
    folder = os.getcwd()
    print("Merging all files")
    merge_all_in_folder(
        folder,
        delete_other_files=True,  # We will only keep one trajectory
        dynamic_imports=FunctionParameter,
        backup=False,
    )
    print("Done")


if __name__ == "__main__":
    main()
