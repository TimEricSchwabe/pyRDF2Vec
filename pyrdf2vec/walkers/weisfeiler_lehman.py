from collections import defaultdict
from hashlib import md5
from typing import Any, DefaultDict, Dict, Iterable, List, Set, Tuple

import attr

from pyrdf2vec.graphs import KG, Vertex
from pyrdf2vec.walkers import RandomWalker


@attr.s
class WLWalker(RandomWalker):
    """Defines the Weisfeler-Lehman walking strategy.

    Args:
        depth: The depth per entity.
        max_walks: The maximum number of walks per entity.
        n_jobs: The number of process to use for multiprocessing.
            Defaults to 1.
        with_reverse: extracts children's and parents' walks from the root,
            creating (max_walks * max_walks) more walks of 2 * depth.
            Defaults to False.
        random_state: The random state to use to ensure ensure random
            determinism to generate the same walks for entities.
            Defaults to None.
        wl_iterations: The Weisfeiler Lehman's iteration.
            Defaults to 4.

    """

    wl_iterations: int = attr.ib(
        kw_only=True, default=4, validator=attr.validators.instance_of(int)
    )

    _inv_label_map: DefaultDict[str, Dict[Any, Any]] = attr.ib(
        init=False, repr=False, factory=lambda: defaultdict(dict)
    )
    _is_support_remote: bool = attr.ib(init=False, repr=False, default=False)
    _label_map: DefaultDict[str, Dict[int, str]] = attr.ib(
        init=False, repr=False, factory=lambda: defaultdict(dict)
    )

    def _create_label(self, kg: KG, vertex: Vertex, n: int) -> str:
        """Creates a label according to a vertex and its neighbors.

        kg: The Knowledge Graph.

            The graph from which the neighborhoods are extracted for the
            provided instances.
        vertex: The vertex to get its neighbors to create the suffix.
        n:  The index of the neighbor

        Returns:
            the label created for the vertex.

        """
        if len(self._label_map) == 0:
            self._weisfeiler_lehman(kg)

        suffix = "-".join(
            sorted(
                set(
                    [
                        self._label_map[neighbor.name][n - 1]
                        for neighbor in kg.get_neighbors(
                            vertex, is_reverse=True
                        )
                    ]
                )
            )
        )
        return f"{self._label_map[vertex.name][n - 1]}-{suffix}"

    def _weisfeiler_lehman(self, kg: KG) -> None:
        """Performs Weisfeiler-Lehman relabeling of the vertices.

        Args:
            kg: The Knowledge Graph.

                The graph from which the neighborhoods are extracted for the
                provided instances.

        """
        for vertex in kg._vertices:
            self._label_map[vertex.name][0] = vertex.name
            self._inv_label_map[vertex.name][0] = vertex.name

        for n in range(1, self.wl_iterations + 1):
            for vertex in kg._vertices:
                self._label_map[vertex.name][n] = str(
                    md5(self._create_label(kg, vertex, n).encode()).digest()
                )

        for vertex in kg._vertices:
            for k, v in self._label_map[vertex.name].items():
                self._inv_label_map[vertex.name][v] = k

    def extract(
        self,
        kg: KG,
        instances: List[str],
        verbose: int = 0,
    ) -> Iterable[str]:
        """Fits the provided sampling strategy and then calls the
        private _extract method that is implemented for each of the
        walking strategies.

        Args:
            kg: The Knowledge Graph.

                The graph from which the neighborhoods are extracted for the
                provided instances.
            instances: The instances to be extracted from the Knowledge Graph.
            verbose: If equal to 1 or 2, display a progress bar for the
                extraction of the walks.

        Returns:
            The 2D matrix with its number of rows equal to the number of
            provided instances; number of column equal to the embedding size.

        """
        self._weisfeiler_lehman(kg)
        return super().extract(kg, instances, verbose)

    def _extract(
        self, kg: KG, instance: Vertex
    ) -> Dict[str, Tuple[Tuple[str, ...], ...]]:
        """Extracts walks rooted at the provided instances which are then each
        transformed into a numerical representation.

        Args:
            kg: The Knowledge Graph.

                The graph from which the neighborhoods are extracted for the
                provided instances.
            instance: The instance to be extracted from the Knowledge Graph.

        Returns:
            The 2D matrix with its number of rows equal to the number of
            provided instances; number of column equal to the embedding size.

        """
        canonical_walks: Set[Tuple[str, ...]] = set()
        walks = self.extract_walks(kg, instance)
        for n in range(self.wl_iterations + 1):
            for walk in walks:
                canonical_walk: List[str] = []
                for i, hop in enumerate(walk):
                    if i == 0 or i % 2 == 1:
                        canonical_walk.append(hop.name)
                    else:
                        canonical_walk.append(self._label_map[hop.name][n])
                canonical_walks.add(tuple(canonical_walk))
        return {instance.name: tuple(canonical_walks)}
