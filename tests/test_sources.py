from unittest.mock import Mock, patch
import pandas as pd
from data_fetcher import EIAClient, FREDClient
from s3_reader import S3DataReader


def test_eia_electricity_filters_and_zero():
    response = Mock()
    response.json.return_value = {'response': {'data': [{'period':'2026-08','price':'0'}]}}
    with patch('data_fetcher.requests.get', return_value=response) as request:
        result = EIAClient('test-key').get_series('ELEC.PRICE.US-RES.M',days=7300)
    assert result.iloc[0]['ELEC.PRICE.US-RES.M'] == 0
    params = request.call_args.kwargs['params']
    assert params['facets[sectorid][]'] == 'RES'
    assert params['facets[stateid][]'] == 'US'
    assert params['data[0]'] == 'price'


def test_fred_missing_markers():
    response = Mock()
    response.json.return_value = {'observations':[{'date':'2026-10-06','value':'.'},{'date':'2026-10-07','value':'0'}]}
    with patch('data_fetcher.requests.get',return_value=response):
        result = FREDClient('test-key').get_series('DGS10')
    assert result['DGS10'].tolist() == [0]


def test_snapshot_date_order_ignores_partition():
    keys = ['raw/year=2026/X_2026-09-01.json','raw/year=2025/X_2026-10-01.json']
    assert sorted(keys,key=S3DataReader._snapshot_order)[-1] == keys[1]


def test_s3_date_request_reads_history_and_latest_revision_wins():
    reader = S3DataReader.__new__(S3DataReader)
    reader.available = True
    reader._list_files = Mock(return_value=['old','new'])
    reader._read_json = Mock(side_effect=[{'observations':[{'date':'2025-09-01','value':'100'},{'date':'2026-09-01','value':'110'}]}, {'observations':[{'date':'2026-09-01','value':'111'}]}])
    result = reader.get_fred_series('CPI',start_date='2025-01-01')
    assert result['CPI'].tolist() == [100,111]


def test_s3_eia_preserves_zero_instead_of_fallback_price():
    reader = S3DataReader.__new__(S3DataReader)
    reader.available = True
    reader._list_files = Mock(return_value=['snapshot'])
    reader._read_json = Mock(return_value={'response':{'data':[{'period':'2026-08','value':0,'price':99}]}})
    result = reader.get_eia_series('POWER')
    assert result.iloc[0]['POWER'] == 0
