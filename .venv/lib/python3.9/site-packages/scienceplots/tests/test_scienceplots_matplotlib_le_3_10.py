"""
Test SciencePlots against Matplotlib<=3.10

Tests MPL API before after namespace changes in 3.11
"""

import matplotlib.pyplot as plt

import pytest
from .conftest import matplotlib_le_3_10

skip_if_mpl_le_3_10 = pytest.mark.skipif(not matplotlib_le_3_10, reason="Matplotlib 3.10 or earlier is not installed")


@skip_if_mpl_le_3_10
def test_matplotlib_required_api_existence():
    """Check if all functions and attributes used by scienceplots are available
    in matplotlib.
    """
    assert hasattr(plt.style, "core")
    assert hasattr(plt.style.core, "read_style_directory")
    assert hasattr(plt.style.core, "update_nested_dict")
    assert hasattr(plt.style, "available")
    assert hasattr(plt.style, "library")


@skip_if_mpl_le_3_10
def test_styles_existence(styles_in_scienceplots_per_folder):
    """Check all styles are available in matplotlib."""
    for folder, styles in styles_in_scienceplots_per_folder.items():
        assert len(styles) > 0, f"No styles found in {folder}."
        for style in styles:
            assert (  # both in list of names and the library they are retrieved from hello
                style in plt.style.available and style in plt.style.library
            ), f"'{style}' not in available styles. Style in folder {folder}."


@skip_if_mpl_le_3_10
def test_usage_of_each_style(
    xy_example_values, styles_in_scienceplots_per_folder, tmp_path,
):
    """Tests if the styles are correctly formatted and can be applied to a plot."""
    pparam = {"xlabel": "Voltage (mV)", "ylabel": r"Current ($\mu$A)"}
    x, ys, p = xy_example_values
    for folder, styles in styles_in_scienceplots_per_folder.items():
        folder = folder.replace("/", "_").replace("\\", "_")  # Fix accessing styles subfolders
        for style in styles:
            output_file = tmp_path / f"test_{folder}_{style}.png"
            with plt.style.context(style):
                fig, ax = plt.subplots()
                for y in ys:
                    ax.plot(x, y)
                ax.legend(p, title="Order")
                ax.set(**pparam)
                ax.autoscale(tight=True)
                fig.savefig(output_file)
                plt.close(fig)
