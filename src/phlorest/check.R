# install.packages('ape')
# if (!require("BiocManager", quietly = TRUE))
#     install.packages("BiocManager")
# BiocManager::install("treeio")
# install.packages('rncl')
# remotes::install_github("ropensci/tracerer")
# install.packages('testthat')

library(ape) # APE: the standard package, no annotations
suppressMessages(library(treeio)) # treeio: considered the 'newer' and 'better' package for trees
library(rncl) # rncl: based on nexus class library, so should be fast but no annotations.
library(tracerer)  # tracerer: loads BEAST annotations

library(testthat)

args <- commandArgs(trailingOnly = TRUE)
treefile <- args[1]
ntrees <- strtoi(args[2])
res <- 0

readers <- list(
  "ape" = function(x) ape::read.nexus(x, force.multi = TRUE),
  "treeio" = function(x) {
    trees <- treeio::read.nexus(x)
    # We force multi "by hand":
    if (class(trees) != 'multiPhylo'){
      trees <- list(c(trees))
      class(trees) <- "multiPhylo"
    }
    trees
  },
  "rncl" = function(x) {
    trees <- rncl::read_nexus_phylo(x)
    # We force multi "by hand":
    if (class(trees) != 'multiPhylo'){
      trees <- list(c(trees))
      class(trees) <- "multiPhylo"
    }
    trees
  },
  "tracerer" = function(x) tracerer::parse_beast_trees(x)
)

for (rdr in names(readers)) {
  # Only use tracerer with files with multiple trees, because it requires tree names to start
  # with STATE_ ...
  if (!(ntrees == 1 && rdr == 'tracerer')) {
    cat(sprintf("READER: %s -- %s\n", rdr, treefile))
    tryCatch(
      expr = {
        t <- readers[[rdr]](treefile)
        # Make sure we read the correct number of trees:
        testthat::expect_equal(length(t), ntrees)
        cat('OK\n')
      },
      error = function(e) {
        res <<- 1
        print(e)
      },
      warning = function(w) {
        print(w)
      }
    )
  }
}
quit(status=res)
