from ..client.exceptions import ParamError

from .check import (
    check_pass_param,
    parser_range_date,
    is_legal_date_range
)

from .types import IndexType


class TableSchema:
    def __init__(self, table_name, dimension, index_file_size, metric_type):
        """
        Table Schema

        :type  table_name: str
        :param table_name: (Required) name of table

            `IndexType`: 0-invalid, 1-flat, 2-ivflat, 3-IVF_SQ8, 4-MIX_NSG

        :type  dimension: int64
        :param dimension: (Required) dimension of vector

        :type  index_file_size: int64
        :param index_file_size: (Optional) max size of files which store index

        :type  metric_type: MetricType
        :param metric_type: (Optional) vectors metric type

            `MetricType`: 1-L2, 2-IP

        """
        check_pass_param(table_name=table_name, dimension=dimension,
                         index_file_size=index_file_size, metric_type=metric_type)

        self.table_name = table_name
        self.dimension = dimension
        self.index_file_size = index_file_size
        self.metric_type = metric_type

    def __repr__(self):
        attr_list = ['%s=%r' % (key, value) for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(attr_list))


class Range:
    """
    Range information

    :type  start_date: str, date or datetime

        `str should be YY-MM-DD format, e.g. "2019-07-01"`

    :param start_date: Range start date

    :type  end_date: str, date or datetime

        `str should be YY-MM-DD format, e.g. "2019-07-01"`

    :param end_date: Range end date

    """

    def __init__(self, start_date, end_date):
        start_date = parser_range_date(start_date)
        end_date = parser_range_date(end_date)
        if is_legal_date_range(start_date, end_date):
            self.start_date = start_date
            self.end_date = end_date
        else:
            raise ParamError("The start-date should be smaller"
                             " than or equal to end-date!")


class QueryResult:

    def __init__(self, _id, _distance):
        self.id = _id
        self.distance = _distance

    def __str__(self):
        return "Result(id={}, distance={})".format(self.id, self.distance)


class RowQueryResult:
    def __init__(self, _id_list, _dis_list):
        self._id_list = _id_list or []
        self._dis_list = _dis_list or []

        # Iterator index
        self.__index = 0

    def __getitem__(self, item):
        if isinstance(item, slice):
            _start = item.start or 0
            _end = min(item.stop, self.__len__()) if item.stop else self.__len__()
            _step = item.step or 1

            elements = []
            for i in range(_start, _end, _step):
                elements.append(self.__getitem__(i))
            return elements

        return QueryResult(self._id_list[item], self._dis_list[item])

    def __len__(self):
        return len(self._id_list)

    def __iter__(self):
        return self

    def __next__(self):
        while self.__index < self.__len__():
            self.__index += 1
            return self.__getitem__(self.__index - 1)

        # iterate stop, raise Exception
        self.__index = 0
        raise StopIteration()


class TopKQueryResult:
    """
    TopK query results, shown as 2-D array

    This Class unpack response from server, store ids and distances separately.
    """

    def __init__(self, raw_source, **kwargs):
        self._raw = raw_source
        self._nq = 0
        self._topk = 0
        self._id_array = []
        self._dis_array = []

        ##
        self.__index = 0

        self._unpack(self._raw)

    def _unpack(self, _raw):
        """

        Args:
            _raw:

        Returns:

        """
        self._nq = _raw.row_num

        # if self._nq == 0:
        #     return

        id_list = list(_raw.ids)
        id_col = len(id_list) // self._nq if self._nq > 0 else 0

        if id_col == 0:
            return

        for i in range(0, len(id_list), id_col):
            self._id_array.append(id_list[i: i + id_col])

        dis_list = list(_raw.distances)
        dis_col = len(dis_list) // self._nq
        for j in range(0, len(dis_list), dis_col):
            self._dis_array.append(dis_list[j: j + dis_col])

        if len(self._id_array) != self._nq or \
                len(self._dis_array) != self._nq:
            raise ParamError("Result parse error.")

        if id_col != dis_col:
            raise ParamError("Result parse error.")

        self._topk = id_col

    @property
    def id_array(self):
        """
        Id array, it's a 2-D array.
        """
        return self._id_array

    @property
    def distance_array(self):
        """
        Distance array, it's a 2-D array
        """
        return self._dis_array

    @property
    def shape(self):
        """
        getter. return result shape, format as (row, column).

        """
        return self._nq, self._topk

    @property
    def raw(self):
        """
        getter. return the raw result response

        """
        return self._raw

    def __len__(self):
        return self._nq

    def __getitem__(self, item):
        if isinstance(item, slice):
            _start = item.start or 0
            _end = min(item.stop, self.__len__()) if item.stop else self.__len__()
            _step = item.step or 1

            elements = []
            for i in range(_start, _end, _step):
                elements.append(self.__getitem__(i))
            return elements

        return RowQueryResult(self._id_array[item], self._dis_array[item])

    def __iter__(self):
        return self

    def __next__(self):
        while self.__index < self.__len__():
            self.__index += 1
            return self.__getitem__(self.__index - 1)

        # iterate stop, raise Exception
        self.__index = 0
        raise StopIteration()

    def __repr__(self):
        """
        :return:
        """

        lam = lambda x: "(id:{}, distance:{})".format(x.id, x.distance)

        if self.__len__() > 5:
            middle = ''

            ll = self[:3]
            for topk in ll:
                if len(topk) > 5:
                    middle = middle + " [ %s" % ",\n   ".join(map(lam, topk[:3]))
                    middle += ",\n   ..."
                    middle += "\n   %s ]\n\n" % lam(topk[-1])
                else:
                    middle = middle + " [ %s ] \n" % ",\n   ".join(map(lam, topk))

            spaces = """        ......
            ......"""

            ahead = "[\n%s%s\n]" % (middle, spaces)
            return ahead

        # self.__len__() < 5
        str_out_list = []
        for i in range(self.__len__()):
            str_out_list.append("[\n%s\n]" % ",\n".join(map(lam, self[i])))

        return "[\n%s\n]" % ",\n".join(str_out_list)


class IndexParam:
    """
    Index Param

    :type  table_name: str
    :param table_name: (Required) name of table

    :type  index_type: IndexType
    :param index_type: (Required) index type, default = IndexType.INVALID

        `IndexType`: 0-invalid, 1-flat, 2-ivflat, 3-IVF_SQ8, 4-MIX_NSG

    :type  nlist: int64
    :param nlist: (Required) num of cell

    """

    def __init__(self, table_name, index_type, nlist):

        if table_name is None:
            raise ParamError('Table name can\'t be None')
        table_name = str(table_name) if not isinstance(table_name, str) else table_name

        if isinstance(index_type, int):
            index_type = IndexType(index_type)
        if not isinstance(index_type, IndexType) or index_type == IndexType.INVALID:
            raise ParamError('Illegal index_type, should be IndexType but not IndexType.INVALID')

        self._table_name = table_name
        self._index_type = index_type
        self._nlist = nlist

    def __str__(self):
        attr_list = ['%s=%r' % (key.lstrip('_'), value)
                     for key, value in self.__dict__.items()]
        return '(%s)' % (', '.join(attr_list))

    def __repr__(self):
        attr_list = ['%s=%r' % (key, value)
                     for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(attr_list))


class PartitionParam:

    def __init__(self, table_name, partition_name, tag):
        self.table_name = table_name
        self.partition_name = partition_name
        self.tag = tag

    def __str__(self):
        attr_list = ['%s=%r' % (key, value)
                     for key, value in self.__dict__.items()]
        return '(%s)' % (', '.join(attr_list))


def _abstract():
    raise NotImplementedError('You need to override this function')


class ConnectIntf:
    """SDK client abstract class

    Connection is a abstract class

    """

    def connect(self, host, port, uri, timeout):
        """
        Connect method should be called before any operations
        Server will be connected after connect return OK
        Should be implemented

        :type  host: str
        :param host: host

        :type  port: str
        :param port: port

        :type  uri: str
        :param uri: (Optional) uri

        :type  timeout: int
        :param timeout:

        :return: Status,  indicate if connect is successful
        """
        _abstract()

    def connected(self):
        """
        connected, connection status
        Should be implemented

        :return: Status,  indicate if connect is successful
        """
        _abstract()

    def disconnect(self):
        """
        Disconnect, server will be disconnected after disconnect return SUCCESS
        Should be implemented

        :return: Status,  indicate if connect is successful
        """
        _abstract()

    def create_table(self, param, timeout):
        """
        Create table
        Should be implemented

        :type  param: TableSchema
        :param param: provide table information to be created

        :type  timeout: int
        :param timeout:

        :return: Status, indicate if connect is successful
        """
        _abstract()

    def has_table(self, table_name, timeout):
        """

        This method is used to test table existence.
        Should be implemented

        :type table_name: str
        :param table_name: table name is going to be tested.

        :type  timeout: int
        :param timeout:

        :return:
            has_table: bool, if given table_name exists

        """
        _abstract()

    def delete_table(self, table_name, timeout):
        """
        Delete table
        Should be implemented

        :type  table_name: str
        :param table_name: table_name of the deleting table

        :type  timeout: int
        :param timeout:

        :return: Status, indicate if connect is successful
        """
        _abstract()

    def add_vectors(self, table_name, records, ids, timeout, **kwargs):
        """
        Add vectors to table
        Should be implemented

        :type  table_name: str
        :param table_name: table name been inserted

        :type  records: list[RowRecord]
        :param records: list of vectors been inserted

        :type  ids: list[int]
        :param ids: list of ids

        :type  timeout: int
        :param timeout:

        :returns:
            Status : indicate if vectors inserted successfully
            ids :list of id, after inserted every vector is given a id
        """
        _abstract()

    def search_vectors(self, table_name, top_k, nprobe, query_records, query_ranges, **kwargs):
        """
        Query vectors in a table
        Should be implemented

        :type  table_name: str
        :param table_name: table name been queried

        :type  query_records: list[RowRecord]
        :param query_records: all vectors going to be queried

        :type  query_ranges: list[Range]
        :param query_ranges: Optional ranges for conditional search.
            If not specified, search whole table

        :type  top_k: int
        :param top_k: how many similar vectors will be searched

        :returns:
            Status:  indicate if query is successful
            query_results: list[TopKQueryResult]
        """
        _abstract()

    def search_vectors_in_files(self, table_name, file_ids, query_records,
                                top_k, nprobe, query_ranges, **kwargs):
        """
        Query vectors in a table, query vector in specified files
        Should be implemented

        :type  table_name: str
        :param table_name: table name been queried

        :type  file_ids: list[str]
        :param file_ids: Specified files id array

        :type  query_records: list[RowRecord]
        :param query_records: all vectors going to be queried

        :type  query_ranges: list[Range]
        :param query_ranges: Optional ranges for conditional search.
            If not specified, search whole table

        :type  top_k: int
        :param top_k: how many similar vectors will be searched

        :returns:
            Status:  indicate if query is successful
            query_results: list[TopKQueryResult]
        """
        _abstract()

    def describe_table(self, table_name, timeout):
        """
        Show table information
        Should be implemented

        :type  table_name: str
        :param table_name: which table to be shown

        :type  timeout: int
        :param timeout:

        :returns:
            Status: indicate if query is successful
            table_schema: TableSchema, given when operation is successful
        """
        _abstract()

    def get_table_row_count(self, table_name, timeout):
        """
        Get table row count
        Should be implemented

        :type  table_name, str
        :param table_name, target table name.

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :returns:
            Status: indicate if operation is successful
            count: int, table row count
        """
        _abstract()

    def show_tables(self, timeout):
        """
        Show all tables in database
        should be implemented

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if this operation is successful
            tables: list[str], list of table names
        """
        _abstract()

    def create_index(self, table_name, index, timeout):
        """
        Create specified index in a table
        should be implemented

        :type  table_name: str
        :param table_name: table name

         :type index: dict
        :param index: index information dict

            example: index = {
                "index_type": IndexType.FLAT,
                "nlist": 18384
            }

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if this operation is successful

        :rtype: Status
        """
        _abstract()

    def client_version(self):
        """
        Provide client version
        should be implemented

        :return:
            Status: indicate if operation is successful

            str : Client version

        :rtype: (Status, str)
        """
        _abstract()

    def server_version(self, timeout):
        """
        Provide server version
        should be implemented

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if operation is successful

            str : Server version

        :rtype: (Status, str)
        """
        _abstract()

    def server_status(self, timeout):
        """
        Provide server status. When cmd !='version', provide 'OK'
        should be implemented

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if operation is successful

            str : Server version

        :rtype: (Status, str)
        """
        _abstract()

    def preload_table(self, table_name, timeout):
        """
        load table to memory cache in advance
        should be implemented

        :param table_name: target table name.
        :type table_name: str

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if operation is successful

        ：:rtype: Status
        """

        _abstract()

    def describe_index(self, table_name, timeout):
        """
        Show index information
        should be implemented

        :param table_name: target table name.
        :type table_name: str

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if operation is successful

            TableSchema: table detail information

        :rtype: (Status, TableSchema)
        """

        _abstract()

    def drop_index(self, table_name, timeout):
        """
        Show index information
        should be implemented

        :param table_name: target table name.
        :type table_name: str

        :type  timeout: int
        :param timeout: how many similar vectors will be searched

        :return:
            Status: indicate if operation is successful

        ：:rtype: Status
        """

        _abstract()
