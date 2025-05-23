import React from 'react';
import { NoContent } from 'UI';
import { getRE } from 'App/utils';
import cn from 'classnames';
import { NO_METRIC_DATA } from 'App/constants/messages';
import { List } from 'immutable';
import { InfoCircleOutlined } from '@ant-design/icons';
import stl from './callWithErrors.module.css';
import MethodType from './MethodType';
import ImageInfo from './ImageInfo';
import { Table } from '../../common';

const cols = [
  {
    key: 'method',
    title: 'Method',
    className: 'text-left',
    Component: MethodType,
    cellClass: 'ml-2',
    width: '8%',
  },
  {
    key: 'urlHostpath',
    title: 'Path',
    Component: ImageInfo,
    width: '40%',
  },
  {
    key: 'allRequests',
    title: 'Requests',
    className: 'text-left',
    width: '15%',
  },
  {
    key: '4xx',
    title: '4xx',
    className: 'text-left',
    width: '15%',
  },
  {
    key: '5xx',
    title: '5xx',
    className: 'text-left',
    width: '15%',
  },
];

interface Props {
  data: any;
  isTemplate?: boolean;
}
function CallWithErrors(props: Props) {
  const { data } = props;
  const [search, setSearch] = React.useState('');
  const test = (value = '', serach: any) => getRE(serach, 'i').test(value);
  const _data = search
    ? data.chart.filter((i: any) => test(i.urlHostpath, search))
    : data.chart;

  const write = ({ target: { name, value } }: any) => {
    setSearch(value);
  };

  return (
    <NoContent
      size="small"
      title={
        <div className="flex items-center gap-2 text-base font-normal">
          <InfoCircleOutlined size={12} /> {NO_METRIC_DATA}
        </div>
      }
      show={data.chart.length === 0}
      style={{ height: '240px' }}
    >
      <div style={{ height: '240px' }}>
        <div className={cn(stl.topActions, 'py-3 flex text-right')}>
          <input
            disabled={data.chart.length === 0}
            className={stl.searchField}
            name="search"
            placeholder="Filter by Path"
            onChange={write}
          />
        </div>
        <Table
          small
          cols={cols}
          rows={List(_data)}
          isTemplate={props.isTemplate}
        />
      </div>
    </NoContent>
  );
}

export default CallWithErrors;
