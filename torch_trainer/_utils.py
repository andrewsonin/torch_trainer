from abc import abstractmethod, ABCMeta
from collections import abc
from os import PathLike
from pathlib import Path
from time import time
from typing import Iterable, Optional, Tuple, Callable, Generator, TypeVar, List, Union

import matplotlib.pyplot as plt
import torch

from IPython.display import clear_output
from matplotlib.ticker import MaxNLocator

mpl_integer_locator = MaxNLocator(integer=True)

Batch = TypeVar('Batch')
FwdResult = TypeVar('FwdResult')
BatchIterable = Iterable[Batch]


class BatchIterator(metaclass=ABCMeta):
    __slots__ = ()

    def __iter__(self) -> Generator[Batch, None, None]:
        return self.batch_generator()

    @abstractmethod
    def batch_generator(self) -> Generator[Batch, None, None]:
        pass


class TorchTrainer:
    __slots__ = (
        # Main attributes
        '_network',
        '_optimizer',
        '_train_function',
        '_loss_function',

        # Data iterators
        '_train_iterator',
        '_test_iterator',
        '_valid_iterator',

        # Constants
        '_n_epochs',
        '_clip_rate',

        # Loss history
        '_valid_loss_history',
        '_train_loss_history',
        '_test_loss_history',

        # Auxiliary info
        '_epoch',
        '_completed',
        '_has_test',
        '_has_valid',
        '_initial_mode',

        # Timing attributes
        '_time_elapsed',

        # Draw settings
        '_alpha',
        '_figsize',
        '_train_loss_color',
        '_valid_loss_color',
        '_test_loss_color',
        '_savefig_path',

        # Temporary attributes,
        '__time_stamp',
        '__train_loss',
        '__test_loss',
        '__val_loss',
        '__speed'
    )

    def __init__(
            self,
            network: torch.nn.Module,
            optimizer: torch.optim.Optimizer,
            *,
            train_function: Callable[['TorchTrainer', Batch], FwdResult],
            loss_function: Callable[['TorchTrainer', Batch, FwdResult], torch.FloatTensor],
            train_iterator: BatchIterable,
            test_iterator: Optional[BatchIterable] = None,
            valid_iterator: Optional[BatchIterable] = None,
            n_epochs: int,
            clip_rate: Optional[float] = None,
            alpha: float = 0.97,
            figsize: Tuple[float, float] = (9, 6),
            train_loss_color: Union[str, float] = 'b',
            valid_loss_color: Union[str, float] = 'r',
            test_loss_color: Union[str, float] = 'g',
            savefig_path: Optional[Union[PathLike, str, Path]] = None
    ) -> None:

        if not isinstance(network, torch.nn.Module):
            raise TypeError('Parameter `network` should be an instance of type `torch.nn.Module`')

        if not isinstance(optimizer, torch.optim.Optimizer):
            raise TypeError('Parameter `optimizer` should be an instance of type `torch.optim.Optimizer`')

        if not isinstance(train_function, abc.Callable):
            raise TypeError('Parameter `train_function` should be callable')

        if not isinstance(loss_function, abc.Callable):
            raise TypeError('Parameter `loss_function` should be callable')

        if not isinstance(train_iterator, BatchIterator):
            raise TypeError('Parameter `train_iterator` should be an instance of `BatchIterator`')

        self._has_test = test_iterator is not None
        if not isinstance(test_iterator, BatchIterator) and self._has_test:
            raise TypeError('Parameter `test_iterator` should be an instance of `BatchIterator` or None')

        self._has_valid = valid_iterator is not None
        if not isinstance(valid_iterator, BatchIterator) and self._has_valid:
            raise TypeError('Parameter `valid_iterator` should be an instance of `BatchIterator` or None')

        if type(n_epochs) is not int:
            raise TypeError('Parameter `n_epochs` should be of type `int`')

        if not isinstance(clip_rate, (int, float)) and clip_rate is not None:
            raise TypeError('Parameter `clip_rate` should be of type `int`, `float` or None')

        if not isinstance(alpha, (int, float)):
            raise TypeError('Parameter `alpha` should be of type `int` or `float`')

        if (
                type(figsize) is not tuple
                or len(figsize) != 2
                or not all(isinstance(cord, (int, float)) for cord in figsize)
        ):
            raise TypeError('Parameter `figsize` should be a `tuple` with two `int` or `float` elements')

        if not isinstance(savefig_path, (Path, str, PathLike)) and savefig_path is not None:
            raise TypeError(
                'Parameter `savefig_path` should be an instance of either PathLike object or `str`, or None'
            )

        self._network = network
        self._initial_mode = network.training
        self._optimizer = optimizer
        self._loss_function = loss_function
        self._train_function = train_function
        self._train_iterator = train_iterator
        self._test_iterator = test_iterator

        self._valid_iterator = valid_iterator
        self._n_epochs = n_epochs
        self._clip_rate = clip_rate

        self._alpha = alpha
        self._figsize = figsize
        self._train_loss_color = train_loss_color
        self._valid_loss_color = valid_loss_color
        self._test_loss_color = test_loss_color
        self._savefig_path = savefig_path

        self._valid_loss_history = []
        self._train_loss_history = []
        self._test_loss_history = []
        self._epoch = 1
        self._completed = False
        self._time_elapsed = 0

        self.__test_loss = self.__val_loss = 0.0

    def forward(self, batch: Batch) -> torch.FloatTensor:
        return self._train_function(self, batch)

    def calc_loss(self, batch: Batch, train_result: torch.FloatTensor) -> torch.FloatTensor:
        return self._loss_function(self, batch, train_result)

    @property
    def network(self) -> torch.nn.Module:
        return self._network

    @property
    def optimizer(self) -> torch.optim.Optimizer:
        return self._optimizer

    @property
    def initial_mode(self) -> bool:
        return self._initial_mode

    @property
    def train_iterator(self) -> BatchIterable:
        return self._train_iterator

    @property
    def test_iterator(self) -> Optional[BatchIterable]:
        return self._test_iterator

    @property
    def valid_iterator(self) -> Optional[BatchIterable]:
        return self._valid_iterator

    @property
    def n_epochs(self) -> int:
        return self._n_epochs

    @property
    def clip_rate(self) -> float:
        return self._clip_rate

    @property
    def train_loss_history(self) -> List[float]:
        return self._train_loss_history.copy()

    @property
    def test_loss_history(self) -> List[float]:
        return self._test_loss_history.copy()

    @property
    def valid_loss_history(self) -> List[float]:
        return self._valid_loss_history.copy()

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def time_elapsed(self) -> float:
        return self._time_elapsed

    @property
    def alpha(self) -> float:
        return self._alpha

    @property
    def figsize(self) -> Tuple[float, float]:
        return self._figsize

    @property
    def train_loss_color(self) -> Union[str, float]:
        return self._train_loss_color

    @property
    def test_loss_color(self) -> Union[str, float]:
        return self._test_loss_color

    @property
    def valid_loss_color(self) -> Union[str, float]:
        return self._valid_loss_color

    def clear_history(self) -> None:
        self._valid_loss_history = []
        self._train_loss_history = []
        self._test_loss_history = []
        self._epoch = 1
        self._completed = False
        self._time_elapsed = 0

    def train(self) -> None:

        # >>> Loading variables onto the stack >>>
        network = self._network
        optimizer = self._optimizer
        train_iterator = self._train_iterator
        valid_iterator = self._valid_iterator
        test_iterator = self._test_iterator
        forward = self.forward
        calc_loss = self.calc_loss
        clip_rate = self._clip_rate
        n_epochs = self._n_epochs
        # <<< Loading variables onto the stack <<<

        self.__time_stamp = time()

        for epoch in range(self._epoch, n_epochs + 1):

            train_loss = 0
            network.train(True)

            for n_batch, train_batch in enumerate(train_iterator, 1):
                optimizer.zero_grad()
                result = forward(train_batch)

                loss = calc_loss(train_batch, result)
                loss.backward()
                if clip_rate is not None:
                    torch.nn.utils.clip_grad_norm_(network.parameters(), clip_rate)
                optimizer.step()

                train_loss += loss.item()

            train_loss /= n_batch
            self.__train_loss = train_loss

            if self._has_valid or self._has_test:
                test_loss = val_loss = 0

                network.train(False)

                with torch.no_grad():
                    if self._has_valid:
                        for n_batch, valid_batch in enumerate(valid_iterator, 1):
                            result = forward(valid_batch)
                            loss = calc_loss(valid_batch, result)
                            val_loss += loss
                        val_loss /= n_batch
                        self.__val_loss = val_loss

                    if self._has_test:
                        for n_batch, test_batch in enumerate(test_iterator, 1):
                            result = forward(test_batch)
                            loss = calc_loss(test_batch, result)
                            test_loss += loss
                        test_loss /= n_batch
                        self.__test_loss = test_loss

            try:
                self.__try_save_loss_history()
            except KeyboardInterrupt:
                self.__retry_save_loss_history()
                self._network.train(self._initial_mode)
                raise
            finally:
                self.__calc_timing_stats()
                self.draw_info()
                self._epoch += 1

        self._completed = True
        network.train(self._initial_mode)

    def __try_save_loss_history(self) -> None:
        self._train_loss_history.append(self.__train_loss)
        if self._has_valid:
            self._valid_loss_history.append(self.__val_loss)
        if self._has_test:
            self._test_loss_history.append(self.__test_loss)

    def __retry_save_loss_history(self) -> None:
        if len(self._train_loss_history) != self._epoch:
            self._train_loss_history.append(self.__train_loss)
        if self._has_valid and len(self._valid_loss_history) < len(self._train_loss_history):
            self._valid_loss_history.append(self.__val_loss)
        if self._has_test and len(self._test_loss_history) < len(self._valid_loss_history):
            self._test_loss_history.append(self.__test_loss)

    def __calc_timing_stats(self) -> None:
        time_stamp = time()
        time_diff = time_stamp - self.__time_stamp
        self.__time_stamp = time_stamp
        self._time_elapsed += time_diff
        self.__speed = 1 / time_diff

    def draw_info(self) -> None:

        _cur_epoch_range = range(1, self._epoch + 1)

        fig = plt.figure(figsize=self._figsize)
        fig.gca().xaxis.set_major_locator(mpl_integer_locator)
        plt.plot(
            _cur_epoch_range,
            self._train_loss_history,
            label='Train',
            color=self._train_loss_color,
            alpha=self._alpha
        )
        if self._has_valid:
            plt.plot(
                _cur_epoch_range,
                self._valid_loss_history,
                label='Valid',
                color=self._valid_loss_color,
                alpha=self._alpha
            )
        if self._has_test:
            plt.plot(
                _cur_epoch_range,
                self._test_loss_history,
                label='Test',
                color=self._test_loss_color,
                alpha=self._alpha
            )
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.legend()
        if self._savefig_path is not None:
            plt.savefig(self._savefig_path)

        log_string = (
            f'Epoch:        {self._epoch - 1:10_}\n'

            f'Train loss:   {self.__train_loss:10.6}      '
            f'Val loss:       {self.__val_loss:10.6}      '
            f'Test loss: {self.__test_loss:10.6}\n'

            f'Time elapsed: {int(self._time_elapsed):10_} sec  '
            f'Time remaining: {int((self._n_epochs - self._epoch) * self.__speed):10_} sec  '
            f'Speed:     {self.__speed:10.6} ep/sec'
        )

        clear_output(True)
        print(log_string)
        plt.show()
