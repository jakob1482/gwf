import abc
import logging

from ..core import PreparedWorkflow
from ..exceptions import WorkflowNotPreparedError
from ..ext import Extension
from ..utils import dfs

logger = logging.getLogger(__name__)


class Backend(Extension):

    """Abstract base class for backends.

    A backend is initialized with an instance of
    :class:`gwf.core.PreparedWorkflow`.
    """

    def __init__(self, workflow):
        """Initialize the backend.

        This method should never be overriden by subclasses.
        """
        if not isinstance(workflow, PreparedWorkflow):
            raise WorkflowNotPreparedError()
        self.workflow = workflow

        all_options = {option_name
                       for target in workflow.targets.values()
                       for option_name in target.options}

        for option_name in all_options:
            if option_name not in self.supported_options:
                logger.warning(
                    'Backend "%s" does not support option "%s".',
                    self.name,
                    option_name
                )

    @property
    def supported_options(self):
        """Return the options supported on targets."""

    @property
    def option_defaults(self):
        """Return defaults for required target options."""
        return {}

    @abc.abstractmethod
    def configure(self, **options):
        """Configure the backend.

        This method *must* be called before any other method on the backend
        is used. Unless the backend is initialized directly, *gwf* is
        responsible for calling :func:`configure` to configure the backend.
        """

    @abc.abstractmethod
    def submitted(self, target):
        """Return whether the target has been submitted."""

    @abc.abstractmethod
    def running(self, target):
        """Return whether the target is running."""

    @abc.abstractmethod
    def submit(self, target):
        """Submit a target."""

    @abc.abstractmethod
    def cancel(self, target):
        """Cancel a target."""

    @abc.abstractmethod
    def logs(self, target, stderr=False, rewind=0):
        """Return log files for a target.

        If `target` has been run multiple times, the latest log will be
        shown by default. To retrieve logs from an earlier run of the target,
        specify how many runs to rewind using the `rewind` parameter. E.g. to
        see the log from three runs ago, specify `rewind=2`. If the backend
        cannot return logs for the specified time point a
        :class:`~gwf.exceptions.NoLogFoundError` is raised.

        By default only standard output (stdout) is returned. If `stderr=True`
        the function will return a tuple (stdout, stderr).

        :param gwf.Target target:
            Target to return logs for.
        :param bool stderr:
            default: False. If true, the method will return a tuple consisting
            of both the standard and error output.
        :param int rewind:
            default: 0. Specify this parameter to obtain logs from earlier
            runs of the target. By default the latest log will be returned.
            To obtain logs from the previous run, specify `rewind=1` etc.
        :return:
            A file-like object or a tuple (stdout, stderr) of file-like objects.
            The user is responsible for closing the returned file(s) after use.
        :raises gwf.exceptions.NoLogFoundError:
            if the backend could not find a log for the given target at the
            given time point.
        """

    def close(self):
        """Close the backend."""

    def schedule(self, target):
        """Schedule and submit a :class:`gwf.Target` and its dependencies.

        This method is provided by :class:`Backend` and should not be overriden.
        """
        logger.debug('Scheduling target %s.', target.name)

        if self.submitted(target):
            logger.debug('Target %s has already been submitted.', target.name)
            return []

        scheduled = []
        for dependency in dfs(target, self.workflow.dependencies):
            logger.info(
                'Scheduling dependency %s of %s',
                dependency.name,
                target.name
            )

            if self.submitted(dependency):
                logger.debug(
                    'Target %s has already been submitted.',
                    dependency.name
                )
                continue

            if not self.workflow.should_run(dependency):
                logger.debug(
                    'Target %s should not run.',
                    dependency.name
                )
                continue

            logger.info('Submitting dependency %s', dependency.name)

            self.submit(dependency)
            scheduled.append(dependency)

        return scheduled

    def schedule_many(self, targets):
        """Schedule a list of :class:`gwf.Target` and their dependencies.

        Will schedule the targets in `targets` with :func:`schedule`
        and return a list of schedules.

        This method is provided by :class:`Backend` and should not be overriden.

        :param list targets: A list of targets to be scheduled.
        :return: A list of schedules, one for each target in `targets`.
        """
        schedules = []
        for target in targets:
            schedules.append(self.schedule(target))
        return schedules
