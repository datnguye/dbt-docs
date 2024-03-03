import os
from abc import ABC, abstractmethod


class BaseTemplate(ABC):
    def __init__(self, module: str) -> None:
        self.template_dir = os.path.abspath(
            "{here}/../template/{template}".format(
                here=os.path.dirname(os.path.realpath(__file__)),
                template=module.split(".")[-1].split("_")[0],
            )
        )

    @abstractmethod
    def generate(self):
        pass
