"""Matchzoo list generator."""

from matchzoo import engine
from matchzoo import datapack
from matchzoo import utils
from matchzoo import tasks

import pandas as pd
import numpy as np
import typing


class ListGenerator(engine.BaseGenerator):
    """ListGenerator for Matchzoo.

    List generator can be used only for ranking.

    TODO: Right now, the :class:`ListGenerator` yield a list each time, that is
    to say, the batch_size is set to be 1. It can be extended to partial or
    multiple lists in each batch.

    Examples:
        >>> np.random.seed(111)
        >>> relation = [['qid0', 'did0', 0],
        ...             ['qid0', 'did1', 1],
        ...             ['qid0', 'did2', 2]
        ... ]
        >>> left = [['qid0', [1, 2]]]
        >>> right = [['did0', [2, 3]],
        ...          ['did1', [3, 4]],
        ...          ['did2', [4, 5]],
        ... ]
        >>> relation = pd.DataFrame(relation,
        ...                         columns=['id_left', 'id_right', 'label'])
        >>> left = pd.DataFrame(left, columns=['id_left', 'text_left'])
        >>> left.set_index('id_left', inplace=True)
        >>> right = pd.DataFrame(right, columns=['id_right', 'text_right'])
        >>> right.set_index('id_right', inplace=True)
        >>> input = datapack.DataPack(relation=relation,
        ...                           left=left,
        ...                           right=right
        ... )
        >>> generator = ListGenerator(input)
        >>> len(generator)
        1
        >>> x, y = generator[0]
        >>> x['text_left'].tolist()
        [[1, 2], [1, 2], [1, 2]]
        >>> x['text_right'].tolist()
        [[2, 3], [3, 4], [4, 5]]
        >>> x['id_left'].tolist()
        ['qid0', 'qid0', 'qid0']
        >>> x['id_right'].tolist()
        ['did0', 'did1', 'did2']
        >>> y.tolist()
        [0.0, 1.0, 2.0]

    """

    def __init__(
        self,
        inputs: datapack.DataPack,
        batch_size: int = 1,
        stage: str = 'train',
        shuffle: bool = True
    ):
        """Construct the list generator.

        :param inputs: the output generated by :class:`DataPack`.
        :param batch_size: number of instances in a batch.
        :param stage: String indicate the pre-processing stage, `train`,
            `evaluate`, or `predict` expected.
        :param shuffle: whether to shuffle the instances while generating a
            batch.
        """
        self._left = inputs.left
        self._right = inputs.right
        self._relation = inputs.relation
        self._task = tasks.Ranking()
        self._id_lists = self.transform_relation(self._relation)
        super().__init__(batch_size, len(self._id_lists), stage, shuffle)

    def transform_relation(self, relations: pd.DataFrame) -> list:
        """Obtain the transformed data from :class:`DataPack`.

        Note here, label is required to make lists.

        :param relations: An instance of DataFrame to be transformed.
        :return: the output of all the lists' indices.
        """
        # Note here the main id is set to be the id_left
        id_lists = []
        for idx, group in relations.groupby('id_left'):
            id_lists.append(group.index.tolist())
        return id_lists

    def _get_batch_of_transformed_samples(
        self,
        index_array: np.array
    ) -> typing.Tuple[dict, typing.Any]:
        """Get a batch of samples based on their ids.

        :param index_array: a list of instance ids.
        :return: A batch of transformed samples.
        """
        trans_index = self._id_lists[index_array[0]]

        batch_y = None
        if self.stage in ['train', 'evaluate']:
            self._relation['label'] = self._relation['label'].astype(
                self._task.output_dtype)
            batch_y = self._relation.iloc[trans_index, 2].values

        left_columns = self._left.columns.values.tolist()
        right_columns = self._right.columns.values.tolist()
        columns = left_columns + right_columns + ['id_left', 'id_right']
        batch_x = dict([(column, []) for column in columns])

        id_left = self._relation.iloc[trans_index, 0]
        id_right = self._relation.iloc[trans_index, 1]

        batch_x['id_left'] = id_left
        batch_x['id_right'] = id_right

        for column in self._left.columns:
            batch_x[column] = self._left.loc[id_left, column].tolist()
        for column in self._right.columns:
            batch_x[column] = self._right.loc[id_right, column].tolist()

        for key, val in batch_x.items():
            batch_x[key] = np.array(val)

        batch_x = utils.dotdict(batch_x)
        return batch_x, batch_y
