.. module:: score.requirejs
.. role:: confkey
.. role:: confdefault

***************
score.requirejs
***************

Provides all necessary tools to start javascript development using
:mod:`score.webassets` and requirejs_.

.. _requirejs: http://requirejs.org/

Quickstart
==========

Configuring the module:

.. code-block:: ini

    [score.init]
    modules =
        score.tpl
        score.js
        score.webassets
        score.requirejs

    [webassets]
    modules = score.requirejs

You can then embed your javascript files in your html with the usual means
provided by :mod:`score.webassets`. The following example uses jinja2 syntax:

.. code-block:: jinja

    <html>
        <head>
            {{ webassets_link('requirejs') }}
            <script>
                require(['some', 'dependencies'], function(some, dependencies) {
                    some(dependencies);
                })
            </script>
        </head>
        <!-- ... -->
    </html>


Configuration
=============

.. autofunction:: init


Details
=======

Client Interaction
------------------

The default behaviour of this module is to provide the requirejs library to the
browser and to load all requested files asynchronously. The example provided in
the quickstart section will render something like the following by default:

.. code-block:: html

    <html>
        <head>
            <script src="/_assets/requirejs/!require.js"></script>
            <script src="/_assets/requirejs/!require-config.js"></script>
            <script>
                require(['some', 'dependencies'], function(some, dependencies) {
                    some(dependencies);
                })
            </script>
        </head>
        <!-- ... -->
    </html>

The first ``script`` tag will load the requirejs library, while the second tag
will load the javascript file containing the requirehs configuration. The
latter would look like the following, provided the file looks like the one in
the documentation of :func:`init`:

.. code-block:: javascript

    requirejs.config({
        map: {
            'some/newmodule': {
                'foo': 'foo1.2'
            },
        },
        shim: {
            'foo': {
                deps: ['bar'],
                exports: 'Foo',
                init: function (bar) {
                    return this.Foo.noConflict();
                }
            }
        }
    });


The bundling behaviour of this module is configured via :mod:`score.webassets`.
If the *tpl.autobundle* configuration of that module evaluates to `True`, the
result of the template will look differently:

.. code-block:: html

    <html>
        <head>
            <script src="/_assets/requirejs/__bundle_d9d396061cc84ccd__"></script>
            <script>
                require(['some', 'dependencies'], function(some, dependencies) {
                    some(dependencies);
                })
            </script>
        </head>
        <!-- ... -->
    </html>

The bundle will consist of the minimal AMD implementation almond_, the requirejs
configuration, *all* javascript files found in the the :mod:`score.tpl` root
folder and all other files matching the additionally configured file
extensions.

.. _almond: https://github.com/requirejs/almond

API
===

.. autofunction:: init

.. autoclass:: ConfiguredRequirejsModule()

    .. automethod:: score_webassets_proxy
