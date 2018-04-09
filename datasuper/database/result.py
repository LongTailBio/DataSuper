from .base_record import *
from pyarchy import archy


class ResultRecord(BaseRecord):
    '''Class that keeps track of a result, essentially a set of files.'''

    def __init__(self, repo, **kwargs):
        super(ResultRecord, self).__init__(repo, **kwargs)
        try:
            self._previousResults = self.db.asPKs(kwargs['previous_results'])
        except KeyError:
            self._previousResults = []

        try:
            self._provenance = kwargs['provenance']
        except KeyError:
            self._provenance = []
        self._resultType = self.repo.validateResultType(kwargs['result_type'])

        try:
            fileRecs = kwargs['file_records']
            try:
                fileRecs = {k: self.db.asPK(v) for k, v in fileRecs.items()}
            except AttributeError:
                fileRecs = [self.db.asPK(el) for el in fileRecs]
        except KeyError:
            raise

        # this will return a list of primary keys or a
        # map of identifiers -> primary keys (as a dict)
        self._fileRecords = self.instantiateResultSchema(fileRecs)

    def to_dict(self):
        '''Create a dict that serializes this result.'''
        out = super(ResultRecord, self).to_dict()
        out['previous_results'] = self._previousResults
        out['provenance'] = self._provenance
        out['file_records'] = self._fileRecords
        out['result_type'] = self._resultType
        return out

    def files(self):
        '''Return a list of tuples of (key, file-record).'''
        if type(self._fileRecords) == dict:
            out = {}
            for k, fr in self._fileRecords.items():
                out[k] = self.db.fileTable.get(fr)
            tups = out.items()
        else:
            tups = enumerate(self.db.fileTable.getMany(self._fileRecords))
        return [(k, v) for k, v in tups]

    def _validStatus(self):
        fs = self.files()
        if len(fs) == 0:
            return True
        if len(fs[0]) == 2:
            fs = [el[1] for el in fs]
        for fileRec in fs:
            if not fileRec.validStatus():
                return False

        # TODO: check that it matches schema
        return True

    def resultType(self):
        '''Return the type of this result.'''
        return self._resultType

    def instantiateResultSchema(self, fileRecs, aggressive=False):
        schema = self.repo.getResultSchema(self.resultType())
        if type(schema) == list:
            if fileRecs is None:
                return [None for _ in schema]
            else:
                assert len(fileRecs) == len(schema), 'Could not build schema for {}'.format(self.resultType())
                return fileRecs
        elif type(schema) == dict:
            if fileRecs is None:
                return {k: None for k in schema.keys()}
            else:
                fileRecsOut = {}
                for k, v in fileRecs.items():
                    if aggressive:
                        msg = 'key {} not found in schema type {}\n'
                        msg = msg.format(k, self.resultType())
                        msg += 'This can occur when a schema is updated.'
                        assert k in schema, msg
                        fileRecsOut[k] = v
                    elif k in schema:
                        fileRecsOut[k] = v
                return fileRecsOut
        else:
            return fileRecs

    def __str__(self):
        out = '{}\t{}'.format(self.name, self._resultType)
        return out

    def tree(self, raw=False):
        '''Returns a JSONable tree starting at this result.'''
        out = {'label': self.name, 'nodes': []}
        for key, fr in self.files():
            out['nodes'].append('{} {}'.format(key, str(fr)))
        if raw:
            return out
        else:
            return archy(out)

    def remove(self, atomic=False):
        '''Remove this result.

        Rewrite this method. Currently removing the record breaks the
        db which should not happen. Not clear if removing the record should
        remove files (if not atomic) but that seems intuitive.

        '''
        if not atomic:
            pk = self.primaryKey
            samples = self.db.sampleTable.getAll()
            for sample in samples:
                try:
                    sample.dropResult(pk)
                except KeyError:
                    # the sample did not have this result
                    pass
            for name, f in self.files():
                f.atomicDelete()
        self.atomicDelete()
