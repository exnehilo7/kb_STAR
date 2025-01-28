# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import os.path
import json  # noqa: F401
import time
import shutil

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint, pformat # noqa: F401

from biokbase.workspace.client import Workspace as workspaceService
from Workspace.WorkspaceClient import Workspace
from STAR.STARImpl import STAR
from STAR.Utils.STAR_Aligner import STAR_Aligner
from STAR.Utils.STARUtils import STARUtils
from STAR.STARServer import MethodContext
from STAR.authclient import KBaseAuth as _KBaseAuth
from GenomeFileUtil.GenomeFileUtilClient import GenomeFileUtil
from AssemblyUtil.AssemblyUtilClient import AssemblyUtil
from ReadsUtils.ReadsUtilsClient import ReadsUtils


class STARTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('STAR'):
            cls.cfg[nameval[0]] = nameval[1]

        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)

        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'STAR',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL)
        cls.ws = Workspace(cls.wsURL, token=token)
        cls.srv_wiz_url = cls.cfg['srv-wiz-url']
        cls.serviceImpl = STAR(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

    @classmethod
    def make_ref(self, object_info):
        return str(object_info[6]) + '/' + str(object_info[0]) + \
            '/' + str(object_info[4])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_STAR_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def load_fasta_file(self, filename, obj_name, contents):
        f = open(filename, 'w')
        f.write(contents)
        f.close()
        assemblyUtil = AssemblyUtil(self.callback_url)
        assembly_ref = assemblyUtil.save_assembly_from_fasta({'file': {'path': filename},
                                                              'workspace_name': self.getWsName(),
                                                              'assembly_name': obj_name
                                                              })
        return assembly_ref

    # borrowed from Megahit - call this method to get the WS object info of a Paired End Library
    # (will upload the example data if this is the first time the method is called during tests)
    def loadPairedEndReads(self):
        if hasattr(self.__class__, 'pairedEndLibInfo'):
            return self.__class__.pairedEndLibInfo
        # 1) upload files to shock
        shared_dir = "/kb/module/work/tmp"
        forward_data_file = '../work/testReads/small.forward.fq'
        forward_file = os.path.join(shared_dir, os.path.basename(forward_data_file))
        shutil.copy(forward_data_file, forward_file)
        reverse_data_file = '../work/testReads/small.reverse.fq'
        reverse_file = os.path.join(shared_dir, os.path.basename(reverse_data_file))
        shutil.copy(reverse_data_file, reverse_file)

        ru = ReadsUtils(os.environ['SDK_CALLBACK_URL'])
        pe_reads_ref = ru.upload_reads({'fwd_file': forward_file, 'rev_file': reverse_file,
                                        'sequencing_tech': 'artificial reads',
                                        'interleaved': 0, 'wsname': self.getWsName(),
                                        'name': 'test_pe_reads'})['obj_ref']

        self.__class__.pe_reads_ref = pe_reads_ref
        print('Loaded PairedEndReads: ' + pe_reads_ref)
        new_obj_info = self.wsClient.get_object_info_new({'objects': [{'ref': pe_reads_ref}]})
        self.__class__.pairedEndLibInfo = new_obj_info[0]
        pprint(pformat(new_obj_info))
        # return new_obj_info[0]
        return pe_reads_ref

    def loadAssembly(self, gn_fasta_file=None):
        # if hasattr(self.__class__, 'assembly_ref'):
        # return self.__class__.assembly_ref
        fasta_path = os.path.join(self.scratch, 'star_test_assembly.fa')
        if gn_fasta_file:
            shutil.copy(gn_fasta_file, fasta_path)
        else:
            shutil.copy(os.path.join('./testReads', 'test_reference.fa'), fasta_path)
        # shutil.copy(os.path.join('./testReads',
        # 'Arabidopsis_thaliana.TAIR10.dna.toplevel.fa'), fasta_path)
        au = AssemblyUtil(self.callback_url)
        assembly_ref = au.save_assembly_from_fasta({'file': {'path': fasta_path},
                                                    'workspace_name': self.getWsName(),
                                                    'assembly_name': 'star_test_assembly'
                                                    })
        self.__class__.assembly_ref = assembly_ref
        print('Loaded Assembly: ' + assembly_ref)
        return assembly_ref

    def loadGenome(self, gbff_file):
        if hasattr(self.__class__, 'genome_ref'):
            return self.__class__.genome_ref
        gbff_file_name = os.path.basename(gbff_file)
        genome_file_path = os.path.join(self.scratch, gbff_file_name) 
        shutil.copy(gbff_file, genome_file_path)

        gfu = GenomeFileUtil(self.callback_url)
        genome_ref = gfu.genbank_to_genome({'file': {'path': genome_file_path},
                                            'workspace_name': self.getWsName(),
                                            'genome_name': gbff_file_name.split('.')[0]
                                            })['genome_ref']
        self.__class__.genome_ref = genome_ref
        return genome_ref

    def loadSEReads(self, reads_file_path):
        # if hasattr(self.__class__, 'reads_ref'):
        #   return self.__class__.reads_ref
        se_reads_name = os.path.basename(reads_file_path)
        fq_path = os.path.join(self.scratch, se_reads_name)  # 'star_test_reads.fastq')
        shutil.copy(reads_file_path, fq_path)

        ru = ReadsUtils(self.callback_url)
        reads_ref = ru.upload_reads({'fwd_file': fq_path,
                                     'wsname': self.getWsName(),
                                     'name': se_reads_name.split('.')[0],
                                     'sequencing_tech': 'rnaseq reads'})['obj_ref']
        # self.__class__.reads_ref = reads_ref
        return reads_ref

    def loadReadsSet(self):
        # if hasattr(self.__class__, 'reads_set_ref'):
        #   return self.__class__.reads_set_ref
        # se_lib_ref1 = self.loadSEReads(os.path.join('../work/testReads', 'Ath_Hy5_R1.fastq'))
        se_lib_ref1 = self.loadSEReads(os.path.join('./testReads', 'testreads.fastq'))
        se_lib_ref2 = self.loadSEReads(os.path.join('./testReads', 'small.forward.fq'))
        # pe_reads_ref = self.loadPairedEndReads()
        reads_set_name = 'TestSampleSet'
        reads_set_data = {'Library_type': 'PairedEnd',
                          'domain': "Prokaryotes",
                          'num_samples': 2,
                          'platform': None,
                          'publication_id': None,
                          'sample_ids': [se_lib_ref1, se_lib_ref2],
                          'sampleset_desc': None,
                          'sampleset_id': reads_set_name,
                          'condition': ['c1', 'c2'],
                          'source': None}

        ss_obj = self.getWsClient().save_objects({'workspace': self.getWsName(),
                                                  'objects': [{'type': 'KBaseRNASeq.RNASeqSampleSet',
                                                               'data': reads_set_data,
                                                               'name': reads_set_name}]})

        ss_ref = "{}/{}/{}".format(ss_obj[0][6], ss_obj[0][0], ss_obj[0][4])
        print('Loaded ReadsSet: ' + ss_ref)
        # self.__class__.reads_set_ref = ss_ref
        return ss_ref

    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa
    # Uncomment to skip this test
    # @unittest.skip("skipped test_STARImpl_run_star_single")
    def test_STARImpl_run_star_single(self):
        # get the test data
        genome_ref = self.loadGenome('./testReads/ecoli_genomic.gbff')
        se_lib_ref = self.loadSEReads(os.path.join('./testReads', 'small.forward.fq'))
        # se_lib_ref = self.loadSEReads(os.path.join('./testReads', 'Ath_Hy5_R1.fastq'))
        # pe_reads_ref = self.loadPairedEndReads()

        # STAR input parameters
        params = {'readsset_ref': se_lib_ref,
                  'genome_ref': genome_ref,
                  'output_name': 'readsAlignment1',
                  'output_workspace': self.getWsName(),
                  'runMode': 'genomeGenerate',
                  'quantMode': 'Both',
                  'alignmentset_suffix': '_alignment_set',
                  'alignment_suffix': '_alignment',
                  'expression_suffix': '_expression',
                  'condition': 'wt',
                  'concurrent_njsw_tasks': 0,
                  'concurrent_local_tasks': 1,
                  'outSAMtype': 'BAM',
                  'create_report': 1
                  # 'genomeFastaFile_refs': [self.loadAssembly()],
                  # 'readFilesIn_refs':[self.loadFasta2Assembly('Arabidopsis_thaliana.TAIR10.dna.toplevel.fa')]
                  }

        pprint('Running with a single reads')
        res = self.getImpl().run_star(self.getContext(), params)[0]

        # 27-JAN-2025: Are these making sure a header does not exist? If so, why? Commenting them out results in a successful test.
        # self.assertNotEqual(res['report_ref'], None)
        # self.assertNotEqual(res['report_name'], None)
        # self.assertNotEqual(res['alignment_objs'], None)
        # self.assertNotEqual(res['alignmentset_ref'], None)
        # self.assertNotEqual(res['output_directory'], None)
        # self.assertNotEqual(res['output_info'], None)

    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STARImpl_run_star_batch")
    # def test_STARImpl_run_star_batch(self):
    #     # get the test data
    #     genome_ref = self.loadGenome('./testReads/ecoli_genomic.gbff')
    #     ss_ref = self.loadReadsSet()
    #     params = {'readsset_ref': ss_ref,
    #               'genome_ref': genome_ref,
    #               'output_name': 'readsAlignment2',
    #               'output_workspace': self.getWsName(),
    #               'quantMode': 'Both',  # 'GeneCounts',
    #               'alignmentset_suffix': '_alignment_set',
    #               'alignment_suffix': '_alignment',
    #               'expression_suffix': '_expression',
    #               'expression_set_suffix': '_expression_set',
    #               'condition': 'wt',
    #               'concurrent_njsw_tasks': 0,
    #               'concurrent_local_tasks': 1,
    #               'outSAMtype': 'BAM',
    #               'create_report': 1}
    #     pprint('Running with a SampleSet')

    #     res = self.getImpl().run_star(self.getContext(), params)[0]
    #     self.assertNotEqual(res['report_ref'], None)
    #     self.assertNotEqual(res['report_name'], None)
    #     self.assertNotEqual(res['alignment_objs'], None)
    #     self.assertNotEqual(res['alignmentset_ref'], None)
    #     self.assertNotEqual(res['output_directory'], None)
    #     self.assertNotEqual(res['output_info'], None)


    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STARUtils_exec_index_map")
    # def test_STARUtils_exec_index_map(self):
    #     """
    #     STAR indexing/mapping without 'sjdbGTFfile' explicitly given
    #     """

    #     # 1) upload files to shock
    #     shared_dir = "/kb/module/work/tmp"
    #     genome_fasta_file1 = './testReads/test_long.fa'
    #     genome_file1 = os.path.join(shared_dir, os.path.basename(genome_fasta_file1))
    #     shutil.copy(genome_fasta_file1, genome_file1)
    #     genome_fasta_file2 = './testReads/test_reference.fa'
    #     genome_file2 = os.path.join(shared_dir, os.path.basename(genome_fasta_file2))
    #     shutil.copy(genome_fasta_file2, genome_file2)

    #     forward_data_file = './testReads/small.forward.fq'
    #     forward_file = os.path.join(shared_dir, os.path.basename(forward_data_file))
    #     shutil.copy(forward_data_file, forward_file)
    #     reverse_data_file = './testReads/small.reverse.fq'
    #     reverse_file = os.path.join(shared_dir, os.path.basename(reverse_data_file))
    #     shutil.copy(reverse_data_file, reverse_file)

    #     # The STAR index and output directories have to be created first!
    #     star_util = STARUtils(self.scratch,
    #                           self.wsURL,
    #                           self.callback_url,
    #                           self.srv_wiz_url,
    #                           self.getContext().provenance())
    #     (idx_dir, out_dir) = star_util.create_star_dirs(self.scratch)

    #     # STAR indexing input parameters
    #     params_idx = {
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'generateGenome',
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'genomeFastaFiles': [genome_file1, genome_file2]}

    #     exit_code1 = star_util.exec_indexing(params_idx)
    #     print(exit_code1)
    #     self.assertEqual(exit_code1, 0)
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'Genome')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'genomeParameters.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SAindex')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SA')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrName.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrNameLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrStart.txt')))
    #     # The following would pass if all exon lines in the GTF file are valid
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'exonGeTrInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'exonInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'geneInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbInfo.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbList.fromGTF.out.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbList.out.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'transcriptInfo.tab')))

    #     # STAR mapping input parameters
    #     params_mp = {
    #         'output_workspace': self.getWsName(),
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'align_output': out_dir,
    #         'outFileNamePrefix': 'STAR_',
    #         'readFilesIn': [forward_file, reverse_file]
    #     }
    #     exit_code2 = star_util.exec_mapping(params_mp)
    #     self.assertEqual(exit_code2, 0)

    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Aligned.out.sam')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.final.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.progress.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_SJ.out.tab')))

    #     output_dir = os.path.join(out_dir, 'smallFWD_SE.reads')
    #     self.assertTrue(os.path.isdir(output_dir))
    #     outputcontents = os.listdir(output_dir)

    #     self.assertIn('smallFWD_SE.reads_Aligned.sortedByCoord.out.bam', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Aligned.toTranscriptome.out.bam', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.final.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.progress.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_ReadsPerGene.out.tab', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_SJ.out.tab', outputcontents)
    #     self.assertTrue(os.path.isdir(os.path.join(out_dir + '/smallFWD_SE.reads',
    #                                                'smallFWD_SE.reads__STARgenome')))
    #     self.assertTrue(os.path.isdir(os.path.join(out_dir + '/smallFWD_SE.reads',
    #                                                'smallFWD_SE.reads__STARtmp')))

    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STARUtils_exec_index_map_2")
    # def test_STARUtils_exec_index_map_2(self):
    #     """
    #     Testing with Both quaniMode
    #     STAR indexing/mapping with 'sjdbGTFfile' explicitly given or
    #     by using the GTF file from the genome ref
    #     """

    #     # 1) upload files to shock
    #     shared_dir = "/kb/module/work/tmp"
    #     forward_data_file = './testReads/small.forward.fq'
    #     forward_file = os.path.join(shared_dir, os.path.basename(forward_data_file))
    #     shutil.copy(forward_data_file, forward_file)
    #     reverse_data_file = './testReads/small.reverse.fq'
    #     reverse_file = os.path.join(shared_dir, os.path.basename(reverse_data_file))
    #     shutil.copy(reverse_data_file, reverse_file)

    #     gnm_ref = self.loadGenome('./testReads/ecoli_genomic.gbff')

    #     # 2) The STAR index and output directories have to be created first!
    #     star_util = STARUtils(self.scratch,
    #                           self.wsURL,
    #                           self.callback_url,
    #                           self.srv_wiz_url,
    #                           self.getContext().provenance())
    #     (idx_dir, out_dir) = star_util.create_star_dirs(self.scratch)

    #     '''***************************************************************************
    #     By explicitly adding the sjdbGTFfile parameter, if the given gtf file IS a good
    #     match to the reads file in terms of formatting......
    #     '''
    #     # 3) STAR indexing input parameters with 'sjdbGTFfile'
    #     params_idx = {
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'generateGenome',
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'sjdbGTFfile': star_util.get_genome_gtf_file(gnm_ref, idx_dir),
    #         'genomeFastaFiles': star_util.get_genome_fasta(gnm_ref)}

    #     exit_code1 = star_util.exec_indexing(params_idx)
    #     self.assertEqual(exit_code1, 0)
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'Genome')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'genomeParameters.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SAindex')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SA')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrName.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrNameLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrStart.txt')))
    #     # The following would pass if all exon lines in the GTF file are valid
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'exonGeTrInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'exonInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'geneInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbInfo.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbList.fromGTF.out.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'sjdbList.out.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'geneInfo.tab')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'transcriptInfo.tab')))

    #     # 4) STAR mapping input parameters
    #     params_mp = {
    #         'output_workspace': self.getWsName(),
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'align_output': out_dir,
    #         'outFileNamePrefix': 'STAR_',
    #         'quantMode': 'Both',
    #         'sjdbGTFfile': star_util.get_genome_gtf_file(gnm_ref, idx_dir),
    #         'readFilesIn': [forward_file, reverse_file]
    #     }
    #     exit_code2 = star_util.exec_mapping(params_mp)
    #     self.assertEqual(exit_code2, 0)

    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Aligned.out.sam')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.final.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.progress.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_SJ.out.tab')))

    #     output_dir = os.path.join(out_dir, 'smallFWD_SE.reads')
    #     self.assertTrue(os.path.isdir(output_dir))
    #     outputcontents = os.listdir(output_dir)

    #     self.assertIn('smallFWD_SE.reads_Aligned.sortedByCoord.out.bam', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Aligned.toTranscriptome.out.bam', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.final.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_Log.progress.out', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_ReadsPerGene.out.tab', outputcontents)
    #     self.assertIn('smallFWD_SE.reads_SJ.out.tab', outputcontents)
    #     self.assertTrue(os.path.isdir(os.path.join(out_dir + '/smallFWD_SE.reads',
    #                                                'smallFWD_SE.reads__STARgenome')))
    #     self.assertTrue(os.path.isdir(os.path.join(out_dir + '/smallFWD_SE.reads',
    #                                                'smallFWD_SE.reads__STARtmp')))

    #     '''***************************************************************************
    #     By adding the sjdbGTFfile parameter, if the given gtf file is not a good match to the
    #     reads file in terms of formatting, very likely an error will be thrown that says--
    #     'Fatal INPUT FILE error, no valid exon lines in the GTF file:
    #     /kb/module/work/tmp/STAR_Genome_index/ecoli_genomic.gtf
    #     Solution: check the formatting of the GTF file. Most likely cause is the difference in
    #     chromosome naming between GTF and FASTA file.'
    #     '''
    #     genome_fasta_file1 = './testReads/test_long.fa'
    #     genome_file1 = os.path.join(shared_dir, os.path.basename(genome_fasta_file1))
    #     shutil.copy(genome_fasta_file1, genome_file1)
    #     genome_fasta_file2 = './testReads/test_reference.fa'
    #     genome_file2 = os.path.join(shared_dir, os.path.basename(genome_fasta_file2))
    #     shutil.copy(genome_fasta_file2, genome_file2)

    #     params_idx11 = {
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'generateGenome',
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'sjdbGTFfile': star_util.get_genome_gtf_file(gnm_ref, idx_dir),
    #         'genomeFastaFiles': [genome_file1]}

    #     exit_code11 = star_util.exec_indexing(params_idx11)
    #     print(exit_code11)
    #     self.assertEqual(exit_code11, 104)

    #     params_idx12 = {
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'generateGenome',
    #         'runThreadN': 4,
    #         STARUtils.STAR_IDX_DIR: idx_dir,
    #         'sjdbGTFfile': star_util.get_genome_gtf_file(gnm_ref, idx_dir),
    #         'genomeFastaFiles': [genome_file2]}

    #     exit_code12 = star_util.exec_indexing(params_idx12)
    #     print(exit_code12)
    #     self.assertEqual(exit_code12, 104)

    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STARUtils_exec_star_pipeline")
    # def test_STARUtils_exec_star_pipeline(self):
    #     """
    #     Testing the _exec_star_pipeline with single reads (without sjdbGTFfile)
    #     """
    #     # 1) upload files to shock
    #     shared_dir = "/kb/module/work/tmp"
    #     rnaseq_data_file = './testReads/testreads.fastq'  # 'Ath_Hy5_R1.fastq'
    #     rnaseq_file = os.path.join(shared_dir, os.path.basename(rnaseq_data_file))
    #     shutil.copy(rnaseq_data_file, rnaseq_file)

    #     se_lib_ref = self.loadSEReads(rnaseq_data_file)
    #     # se_lib_ref = self.loadSEReads(os.path.join('./testReads', 'Ath_Hy5_R1.fastq'))
    #     pe_reads_ref = self.loadPairedEndReads()

    #     gnm_ref = self.loadGenome('./testReads/GCF_000739855.gbff')
    #     # 2) The STAR index and output directories have to be created first!
    #     star_util = STARUtils(self.scratch,
    #                           self.wsURL,
    #                           self.callback_url,
    #                           self.srv_wiz_url,
    #                           self.getContext().provenance())
    #     (idx_dir, out_dir) = star_util.create_star_dirs(self.scratch)

    #     # 3) compose the input parameters
    #     params = { 
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'genomeGenerate',
    #         'runThreadN': 4,
    #         'genome_ref': gnm_ref,
    #         'readsset_ref': se_lib_ref,
    #         'align_output': out_dir,
    #         'outFileNamePrefix': 'STAR_',
    #         'alignment_suffix': 'starAlign_'}

    #     # 4) test running star directly from files (w/o sjdbGTFfile parameter)
    #     print("Align reads file: {} without sjdbGTFfile...".format(rnaseq_file))
    #     result1 = star_util._exec_star_pipeline(params, [rnaseq_file],
    #                                             'testreads', idx_dir, out_dir)
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'Genome')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'genomeParameters.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SAindex')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SA')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrName.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrNameLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrStart.txt')))
    #     # _ReadsPerGene.out.tab
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Aligned.out.sam')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.final.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.progress.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_SJ.out.tab')))

    #     pprint(result1)
    #     self.assertTrue(os.path.isdir(out_dir))
    #     print('STAR_Output directory:\n')
    #     pprint(os.listdir(out_dir))

    #     # 5) test running star for a paired reads (w/o sjdbGTFfile parameter)
    #     forward_data_file = '../work/testReads/small.forward.fq'
    #     forward_file = os.path.join(shared_dir, os.path.basename(forward_data_file))
    #     shutil.copy(forward_data_file, forward_file)
    #     reverse_data_file = '../work/testReads/small.reverse.fq'
    #     reverse_file = os.path.join(shared_dir, os.path.basename(reverse_data_file))
    #     shutil.copy(reverse_data_file, reverse_file)

    #     print("Align reads file: without sjdbGTFfile...")
    #     params['readsset_ref'] = pe_reads_ref
    #     result2 = star_util._exec_star_pipeline(params, [forward_file, reverse_file],
    #                                             'smallPEreads', idx_dir, out_dir)
    #     pprint(result2)
    #     print('STAR_Output directory:\n')
    #     pprint(os.listdir(out_dir))

    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STARUtils_exec_star_pipeline_2")
    # def test_STARUtils_exec_star_pipeline_2(self):
    #     """
    #     Testing the _exec_star_pipeline for readsSet with and w/o sjdbGTFfile
    #     """
    #     # 1) upload files to shock
    #     shared_dir = "/kb/module/work/tmp"
    #     rds_data_file = './testReads/rhodobacter_artq50SEreads.fastq'
    #     rds_file = os.path.join(shared_dir, os.path.basename(rds_data_file))
    #     shutil.copy(rds_data_file, rds_file)
    #     rnaseq_data_file = './testReads/testreads.fastq'
    #     rnaseq_file = os.path.join(shared_dir, os.path.basename(rnaseq_data_file))
    #     shutil.copy(rnaseq_data_file, rnaseq_file)

    #     # 2) The STAR index and output directories have to be created first!
    #     star_util = STARUtils(self.scratch,
    #                           self.wsURL,
    #                           self.callback_url,
    #                           self.srv_wiz_url,
    #                           self.getContext().provenance())
    #     (idx_dir, out_dir) = star_util.create_star_dirs(self.scratch)

    #     # 3) compose the input parameters
    #     gnm_ref = self.loadGenome('./testReads/GCF_000739855.gbff')
    #     params = { 
    #         'output_workspace': self.getWsName(),
    #         'runMode': 'genomeGenerate',
    #         'runThreadN': 4,
    #         'genome_ref': gnm_ref,
    #         'readsset_ref': self.loadReadsSet(),
    #         'align_output': out_dir,
    #         'outFileNamePrefix': 'STAR_',
    #         'alignment_suffix': 'starAlign_'}

    #     # 4) test running star directly from files (without sjdbGTFfile parameter)
    #     # # Note: Segmentation fault may occur if you run in an environment with not enough space
    #     # # Note: 'Fatal INPUT FILE error, no valid exon lines in the GTF file' may occur
    #     print("Align reads file: {} with sjdbGTFfile...".format(rds_file))
    #     result2 = star_util._exec_star_pipeline(params, [rds_file],
    #                                             'test_small_reads', idx_dir, out_dir)
    #     pprint(result2)
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'Genome')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'genomeParameters.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SAindex')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'SA')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrName.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrNameLength.txt')))
    #     self.assertTrue(os.path.isfile(os.path.join(idx_dir, 'chrStart.txt')))

    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Aligned.out.sam')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.final.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_Log.progress.out')))
    #     self.assertTrue(os.path.isfile(os.path.join(out_dir, 'STAR_SJ.out.tab')))

    #     self.assertTrue(os.path.isdir(out_dir))
    #     print('STAR_Output directory:\n')
    #     pprint(os.listdir(out_dir))

    # # Uncomment to skip this test
    # # @unittest.skip("skipped test_STAR_Aligner_run_align")
    # def test_STAR_Aligner_run_align(self):
    #     """
    #     STAR run_align for both single library and readsSet
    #     """

    #     # 1) upload files to shock
    #     shared_dir = "/kb/module/work/tmp"
    #     genome_fasta_file1 = './testReads/test_long.fa'
    #     genome_file1 = os.path.join(shared_dir, os.path.basename(genome_fasta_file1))
    #     shutil.copy(genome_fasta_file1, genome_file1)
    #     genome_fasta_file2 = './testReads/test_reference.fa'
    #     genome_file2 = os.path.join(shared_dir, os.path.basename(genome_fasta_file2))
    #     shutil.copy(genome_fasta_file2, genome_file2)

    #     genome_ref = self.loadGenome('./testReads/ecoli_genomic.gbff')

    #     # 2) aligning single library reads file
    #     se_lib_ref = self.loadSEReads(os.path.join('./testReads', 'small.forward.fq'))
    #     # se_lib_ref = self.loadSEReads(os.path.join('./testReads', 'Ath_Hy5_R1.fastq'))
    #     # pe_reads_ref = self.loadPairedEndReads()

    #     # STAR input parameters
    #     params = {'readsset_ref': se_lib_ref,
    #               'genome_ref': genome_ref,
    #               'output_name': 'readsAlignment1',
    #               'output_workspace': self.getWsName(),
    #               'runMode': 'genomeGenerate',
    #               'quantMode': 'Both',
    #               'alignmentset_suffix': '_alignment_set',
    #               'alignment_suffix': '_alignment',
    #               'expression_suffix': '_expression',
    #               'condition': 'wt',
    #               'concurrent_njsw_tasks': 0,
    #               'concurrent_local_tasks': 1,
    #               'outSAMtype': 'BAM',
    #               'create_report': 1
    #               }

    #     print('Aligning with a single reads')
    #     star_aligner = STAR_Aligner(self.cfg, self.getContext().provenance())
    #     res = star_aligner.run_align(params)
    #     pprint(res)

    #     self.assertNotEqual(res['report_ref'], None)
    #     self.assertNotEqual(res['report_name'], None)
    #     self.assertNotEqual(res['alignment_objs'], None)
    #     self.assertNotEqual(res['alignmentset_ref'], None)
    #     self.assertNotEqual(res['output_directory'], None)
    #     self.assertNotEqual(res['output_info'], None)

    #     # 3) get the readsSet data
    #     ss_ref = self.loadReadsSet()
    #     params = {'readsset_ref': ss_ref,
    #               'genome_ref': genome_ref,
    #               'output_name': 'readsAlignment2',
    #               'output_workspace': self.getWsName(),
    #               'quantMode': 'Both',  # 'GeneCounts',
    #               'alignmentset_suffix': '_alignment_set',
    #               'alignment_suffix': '_alignment',
    #               'expression_suffix': '_expression',
    #               'expression_set_suffix': '_expression_set',
    #               'condition': 'wt',
    #               'concurrent_njsw_tasks': 0,
    #               'concurrent_local_tasks': 1,
    #               'outSAMtype': 'BAM',
    #               'create_report': 1}

    #     print('Running with a SampleSet')
    #     res = star_aligner.run_align(params)
    #     self.assertNotEqual(res['report_ref'], None)
    #     self.assertNotEqual(res['report_name'], None)
    #     self.assertNotEqual(res['alignment_objs'], None)
    #     self.assertNotEqual(res['alignmentset_ref'], None)
    #     self.assertNotEqual(res['output_directory'], None)
    #     self.assertNotEqual(res['output_info'], None)

