const esbuild = require('esbuild');

const isWatch = process.argv.includes('-w');
const isBuild = !isWatch;
const mode = isBuild ? 'production' : 'development';


const buildOptions = {
    entryPoints: ['reactor/static/reactor/reactor.js'],
    define: {
        'process.env.NODE_ENV': JSON.stringify(mode),
    },
    bundle: true,
    sourcemap: true,
    minify: isBuild,
    incremental: isWatch,
    outfile: 'reactor/static/reactor/reactor.min.js',
    watch: isWatch,
};

esbuild.build(buildOptions);
