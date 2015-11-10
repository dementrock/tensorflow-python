"""A key-value[] store that implements reservoir sampling on the values."""

import collections
import random
import threading


class Reservoir(object):
  """A map-to-arrays container, with deterministic Reservoir Sampling.

  Items are added with an associated key. Items may be retrieved by key, and
  a list of keys can also be retrieved. If size is not zero, then it dictates
  the maximum number of items that will be stored with each key. Once there are
  more items for a given key, they are replaced via reservoir sampling, such
  that each item has an equal probability of being included in the sample.

  Deterministic means that for any given seed and bucket size, the sequence of
  values that are kept for any given tag will always be the same, and that this
  is independent of any insertions on other tags. That is:

  >>> separate_reservoir = reservoir.Reservoir(10)
  >>> interleaved_reservoir = reservoir.Reservoir(10)
  >>> for i in xrange(100):
  >>>   separate_reservoir.AddItem('key1', i)
  >>> for i in xrange(100):
  >>>   separate_reservoir.AddItem('key2', i)
  >>> for i in xrange(100):
  >>>   interleaved_reservoir.AddItem('key1', i)
  >>>   interleaved_reservoir.AddItem('key2', i)

  separate_reservoir and interleaved_reservoir will be in identical states.

  See: https://en.wikipedia.org/wiki/Reservoir_sampling

  Adding items has amortized O(1) runtime.

  """

  def __init__(self, size, seed=0):
    """Creates a new reservoir.

    Args:
      size: The number of values to keep in the reservoir for each tag. If 0,
        all values will be kept.
      seed: The seed of the random number generator to use when sampling.
        Different values for |seed| will produce different samples from the same
        input items.

    Raises:
      ValueError: If size is negative or not an integer.
    """
    if size < 0 or size != round(size):
      raise ValueError('size must be nonegative integer, was %s' % size)
    self._buckets = collections.defaultdict(
        lambda: _ReservoirBucket(size, random.Random(seed)))
    # _mutex guards the keys - creating new keys, retreiving by key, etc
    # the internal items are guarded by the ReservoirBuckets' internal mutexes
    self._mutex = threading.Lock()

  def Keys(self):
    """Return all the keys in the reservoir.

    Returns:
      ['list', 'of', 'keys'] in the Reservoir.
    """
    with self._mutex:
      return self._buckets.keys()

  def Items(self, key):
    """Return items associated with given key.

    Args:
      key: The key for which we are finding associated items.

    Raises:
      KeyError: If the key is not ofund in the reservoir.

    Returns:
      [list, of, items] associated with that key.
    """
    with self._mutex:
      if key not in self._buckets:
        raise KeyError('Key %s was not found in Reservoir' % key)
      bucket = self._buckets[key]
    return bucket.Items()

  def AddItem(self, key, item):
    """Add a new item to the Reservoir with the given tag.

    The new item is guaranteed to be kept in the Reservoir. One other item might
    be replaced.

    Args:
      key: The key to store the item under.
      item: The item to add to the reservoir.
    """
    with self._mutex:
      bucket = self._buckets[key]
    bucket.AddItem(item)


class _ReservoirBucket(object):
  """A container for items from a stream, that implements reservoir sampling.

  It always stores the most recent item as its final item.
  """

  def __init__(self, _max_size, _random=None):
    """Create the _ReservoirBucket.

    Args:
      _max_size: The maximum size the reservoir bucket may grow to. If size is
        zero, the bucket has unbounded size.
      _random: The random number generator to use. If not specified, defaults to
        random.Random(0).

    Raises:
      ValueError: if the size is not a nonnegative integer.
    """
    if _max_size < 0 or _max_size != round(_max_size):
      raise ValueError('_max_size must be nonegative int, was %s' % _max_size)
    self.items = []
    # This mutex protects the internal items, ensuring that calls to Items and
    # AddItem are thread-safe
    self._mutex = threading.Lock()
    self._max_size = _max_size
    self._count = 0
    if _random is not None:
      self._random = _random
    else:
      self._random = random.Random(0)

  def AddItem(self, item):
    """Add an item to the ReservoirBucket, replacing an old item if necessary.

    The new item is guaranteed to be added to the bucket, and to be the last
    element in the bucket. If the bucket has reached capacity, then an old item
    will be replaced. With probability (_max_size/_count) a random item in the
    bucket will be popped out and the new item will be appended to the end. With
    probability (1 - _max_size/_count) the last item in the bucket will be
    replaced.

    Since the O(n) replacements occur with O(1/_count) liklihood, the amortized
    runtime is O(1).

    Args:
      item: The item to add to the bucket.
    """
    with self._mutex:
      if len(self.items) < self._max_size or self._max_size == 0:
        self.items.append(item)
      else:
        r = self._random.randint(0, self._count)
        if r < self._max_size:
          self.items.pop(r)
          self.items.append(item)
        else:
          self.items[-1] = item
      self._count += 1

  def Items(self):
    """Get all the items in the bucket."""
    with self._mutex:
      return self.items
