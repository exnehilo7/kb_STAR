/*
   Name of module: STAR

   This KBase module wraps the free open source software STAR: ultrafast universal RNA-seq aligner.
   STAR-2.6.1a

   References:
   https://github.com/alexdobin/STAR/
   https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf
*/

module STAR {
    /* 
        A 'typedef' allows you to provide a more specific name for
        a type.  Built-in primitive types include 'string', 'int',
        'float'.  Here we define a type named assembly_ref to indicate
        a string that should be set to a KBase ID reference to an
        Assembly data object.
    */
    typedef string assembly_ref;

    /* A boolean - 0 for false, 1 for true.
        @range (0, 1)
    */
		    
    typedef int bool;

	        /* An X/Y/Z style reference
    */
    typedef string obj_ref;

    /*
        Will align the input reads (or set of reads specified in a SampleSet) to the specified
        assembly or assembly for the specified Genome (accepts Assembly, ContigSet, or Genome types)
        and produces a ReadsAlignment object, or in the case of a SampleSet, a ReadsAlignmentSet object

        obj_ref genome_ref: KBase workspace reference Genome
        obj_ref readsset_ref: the workspace reference for the set of reads to align, referring to 
                            either a SingleEnd/PairedEnd reads, or a ReadsSet input
        string output_workspace - name or id of the WS to save the results to, provided by the narrative for housing output in KBase
        string output_name - name of the output ReadsAlignment or ReadsAlignmentSet object
        int runThreadN - the number of threads for STAR to use (default to 2)
        string outFileNamePrefix: you can change the file prefixes using --outFileNamePrefix /path/to/output/dir/prefix
                                By default, this parameter is ./, i.e. all output files are written in current directory without a prefix
        string quantMode: types of quantification requested--none/TranscriptomeSAM/GeneCounts
        int outFilterMultimapNmax: max number of multiple alignments allowed for a read: if exceeded,
                                the read is considered unmapped, default to 20
        int alignSJoverhangMin: minimum overhang for unannotated junctions, default to 8
        int alignSJDBoverhangMin: minimum overhang for annotated junctions, default to 1
        int outFilterMismatchNmax: maximum number of mismatches per pair, large number switches off this filter, default to 999
        int alignIntronMin: minimum intron length, default to 20
        int alignIntronMax: maximum intron length, default to 1000000
        int alignMatesGapMax: maximum genomic distance between mates, default to 1000000
        int create_report: = 1 if we build a report, 0 otherwise. (default 1) (shouldn not be user set - mainly used for subtasks)

        @optional alignmentset_suffix
        @optional alignIntronMin
        @optional alignIntronMax
        @optional alignMatesGapMax
        @optional alignSJoverhangMin
        @optional alignSJDBoverhangMin
        @optional quantMode
        @optional outFilterType
        @optional outFilterMultimapNmax
        @optional outSAMtype
        @optional outSAMattrIHstart
        @optional outSAMstrandField
        @optional outFilterMismatchNmax
        @optional outFileNamePrefix
        @optional runThreadN
    */
    typedef structure {
        obj_ref readsset_ref;
        obj_ref genome_ref;
        string output_workspace;
        string output_name;
        string alignment_suffix;
        string condition;
        int concurrent_njsw_tasks;
        int concurrent_local_tasks;
        string outSAMunmapped;
        bool create_report;

        string alignmentset_suffix;
        int alignIntronMin;
        int alignIntronMax;
        int alignMatesGapMax;
        int alignSJoverhangMin;
        int alignSJDBoverhangMin;
        string quantMode;
        string outFilterType;
        int outFilterMultimapNmax;
        string outSAMtype;
        int outSAMattrIHstart;
        string outSAMstrandField;
        int outFilterMismatchNmax;
        string outFileNamePrefix;
        int runThreadN;
    } AlignReadsParams;

    /*
        Created alignment object returned.
        ref = the workspace reference of the new alignment object
        name = the name of the new object, for convenience.
    */
    typedef structure {
        obj_ref ref;
        string name;
    } AlignmentObj;

    /*
        Here is the definition of the output of the function.  The output
        can be used by other SDK modules which call your code, or the output
        visualizations in the Narrative.  'report_name' and 'report_ref' are
        special output fields- if defined, the Narrative can automatically
        render your Report.

        output_directory: folder path that holds all output files generated by run_star
        alignmentset_ref: if an alignment set is created
        alignment_objs: for each individual alignment created. The keys are the references to the reads
                        object being aligned.
        report_name: report name generated by KBaseReport
        report_ref: report reference generated by KBaseReport
    */
    typedef structure {
        string output_directory;
        string report_name;
        obj_ref report_ref;
        obj_ref alignmentset_ref;
        mapping<obj_ref reads_ref, AlignmentObj> alignment_objs;
    } AlignReadsResult;

    funcdef run_star(AlignReadsParams params)
        returns (AlignReadsResult returnVal) authentication required;
};
