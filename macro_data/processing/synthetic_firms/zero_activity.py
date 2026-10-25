"""Source-zero rows use the existing provincial empty-sector convention."""
import numpy as np
from macro_data.readers.default_readers import _floor_empty_provincial_sectors,CAN_2022_EMPTY_SECTOR_FLOOR


def floor_source_zero(table,source_output,regions,industries):
    """Use exact observed zeros, rather than residual allocation roundoff.

    The inherited helper books equal output/VA and domestic fixed capital
    formation. It never touches people, contracts or financial stocks.
    """
    result=table.copy(deep=True);zero=[]
    for region in regions:
        for industry in industries:
            cell=(str(region),industry)
            if source_output.loc[cell]==0:
                zero.append(cell)
                if result.at[cell,('TOTAL','Output')]!=CAN_2022_EMPTY_SECTOR_FLOOR:
                    result.at[cell,('TOTAL','Output')]=0.
    _floor_empty_provincial_sectors(result,industries,{'CAN':list(regions)})
    assert all(result.at[cell,('TOTAL','Output')]==CAN_2022_EMPTY_SECTOR_FLOOR for cell in zero)
    return result,zero
